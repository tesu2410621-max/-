import datetime
import json
import tempfile
import unittest
from pathlib import Path

from ronbun_news.__main__ import _with_faculties, build, essay_slots, main
from ronbun_news.enrich import research, template_english, template_essay, write
from ronbun_news.exam import in_window, season
from ronbun_news.feeds import parse_feed
from ronbun_news.picker import pick_english, pick_essays, score

HERE = Path(__file__).parent
JA = HERE / "sample_feed.xml"
EN = HERE / "sample_feed_en.xml"
D = datetime.date


def ja():
    return parse_feed(JA.read_bytes(), "サンプル")


def en():
    return parse_feed(EN.read_bytes(), "Sample")


def offline():
    raise AssertionError("復習モードで在庫が十分なら、ネットから取得してはいけない")


class PickTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(len(ja()), 11)
        self.assertTrue(ja()[0]["published"].startswith("2026-09-30"))

    def test_one_article_per_faculty(self):
        chosen = pick_essays(ja())
        self.assertEqual(set(chosen), {"bun", "hou", "kankyo", "sogo"})
        titles = [a["title"] for a in chosen.values()]
        self.assertEqual(len(set(titles)), 4)
        self.assertFalse(any("野球" in t or "逮捕" in t for t in titles))
        self.assertIn("言葉", chosen["bun"]["title"])

    def test_recent_titles_are_skipped(self):
        chosen = pick_essays(ja(), exclude_titles=["【サンプル】国語に関する世論調査、言葉の使い方に世代差"])
        self.assertNotIn("言葉", chosen.get("bun", {"title": ""})["title"])

    def test_english_diverse_no_noise_no_duplicates(self):
        chosen = pick_english(en(), n=3)
        titles = [a["title"] for a in chosen]
        self.assertEqual(len(chosen), 3)
        self.assertEqual(len({a["theme"] for a in chosen}), 3)
        self.assertFalse(any("Premier" in t for t in titles))
        self.assertEqual(sum("Central bank" in t for t in titles), 1)

    def test_ascii_keyword_boundary(self):
        self.assertEqual(score({"title": "EMAIL配信の新機能", "summary": ""})[1], None)


class ExamSeasonTest(unittest.TestCase):
    def test_season(self):
        self.assertEqual(season(D(2026, 9, 30)), ("live", D(2025, 12, 1), D(2026, 11, 30), 2027))
        self.assertEqual(season(D(2026, 11, 30))[0], "live")
        self.assertEqual(season(D(2026, 12, 1))[0], "review")
        self.assertEqual(season(D(2027, 2, 10))[:3], ("review", D(2025, 12, 1), D(2026, 11, 30)))
        self.assertEqual(season(D(2027, 4, 1))[2], D(2027, 11, 30))

    def test_in_window(self):
        self.assertTrue(in_window("2026-11-15", D(2027, 1, 10)))
        self.assertFalse(in_window("2026-12-15", D(2027, 1, 10)))


class BuildTest(unittest.TestCase):
    def test_live_day(self):
        entry = build(D(2026, 9, 30), [], ja, en)
        self.assertEqual(entry["mode"], "live")
        self.assertEqual(entry["issue"], 1)
        self.assertEqual([a["faculty"] for a in entry["essays"]], essay_slots(D(2026, 9, 30)))
        self.assertEqual(len(entry["english"]), 2)
        self.assertTrue(all(a["paper"]["headline"] for a in entry["essays"] + entry["english"]))

    def test_faculties_rotate_every_two_days(self):
        seen = set()
        for d in (1, 2):
            entry = build(D(2026, 10, d), [], ja, en)
            seen |= {a["faculty"] for a in entry["essays"]}
        self.assertEqual(seen, {"bun", "hou", "kankyo", "sogo"})

    def test_review_mode_reuses_papers_without_repeats(self):
        history = []
        for d in range(1, 5):
            day = D(2026, 11, d)
            history.insert(0, (day.isoformat(), build(day, history, ja, en)))
        dec1 = build(D(2026, 12, 1), history, offline, offline)
        self.assertEqual(dec1["mode"], "review")
        self.assertTrue(all(a.get("from_date") and a["paper"] for a in dec1["essays"] + dec1["english"]))
        history.insert(0, ("2026-12-01", dec1))
        dec5 = build(D(2026, 12, 5), history, ja, en)  # 12/1 と同じ学部の枠
        self.assertFalse({a["link"] for a in dec1["essays"]} & {a["link"] for a in dec5["essays"] if a.get("from_date")})

    def test_review_falls_back_to_fresh_news_marked_outside(self):
        entry = build(D(2027, 1, 10), [], ja, en)
        self.assertEqual(entry["mode"], "review")
        self.assertTrue(all(a["outside_window"] for a in entry["essays"]))

    def test_build_site(self):
        with tempfile.TemporaryDirectory() as out:
            args = ["--out", out, "--feed-file", str(JA), "--english-feed-file", str(EN)]
            self.assertEqual(main(["--date", "2026-09-30", *args]), 0)
            self.assertEqual(main(["--date", "2026-10-01", *args]), 0)
            root = Path(out)
            data = json.loads((root / "data" / "2026-09-30.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data["essays"]), 2)
            index = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn("慶應入試新聞", index)
            self.assertIn("第2号", index)
            self.assertIn("2026年（令和8年）10月1日　木曜日", index)
            self.assertIn("出題圏の締め切り", index)
            self.assertIn("英語長文面", index)
            self.assertIn("pdf/2026-10-01.pdf", index)
            archive = (root / "archive.html").read_text(encoding="utf-8")
            self.assertLess(archive.index("2026-10-01"), archive.index("2026-09-30"))


class ClaudePaperTest(unittest.TestCase):
    """Claude の呼び出し（取材→執筆）の流れを、偽のクライアントで確かめる。"""

    def test_research_resumes_pause_turn_then_writes_paper(self):
        essays = [_with_faculties(a) for a in pick_essays(ja(), ["sogo", "kankyo"]).values()]
        english = pick_english(en(), 2)
        paper = {
            "theme": "テスト",
            "essays": [template_essay(a) for a in essays],
            "english": [template_english(a) for a in english],
            "history": {"index_line": "産業革命", "paragraphs": ["**産業革命**の話。"]},
        }
        client = FakeClient([
            FakeResponse("pause_turn", [FakeBlock("text", "メモ前半")]),
            FakeResponse("end_turn", [FakeBlock("text", "メモ後半")]),
            FakeResponse("end_turn", [FakeBlock("text", json.dumps(paper, ensure_ascii=False))]),
        ])
        notes = research(client, essays, english)
        self.assertEqual(notes, "メモ前半\nメモ後半")
        resumed = client.calls[1]["messages"]
        self.assertEqual([m["role"] for m in resumed], ["user", "assistant"])
        self.assertEqual(write(client, essays, english, notes)["theme"], "テスト")
        self.assertIn("メモ後半", client.calls[2]["messages"][0]["content"])
        self.assertEqual(client.calls[2]["output_config"]["format"]["type"], "json_schema")

    def test_refusal_raises(self):
        client = FakeClient([FakeResponse("refusal", [])])
        with self.assertRaises(RuntimeError):
            research(client, [], [])


class FakeBlock:
    def __init__(self, type, text):
        self.type, self.text = type, text


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason, self.content = stop_reason, content


class FakeClient:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.beta = self
        self.messages = self

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


class RealWorldRegressionTest(unittest.TestCase):
    """初回の本番実行（2026-09-30）で見つかった選び方の問題。"""

    ARTICLES = [
        {"title": "【岡山大学】岡山大学と奈良先端科学技術大学院大学が包括連携協定を締結-地域中核・特色ある研究大学強化促進事業（J-PEAKS）採択大学間で次世代セキュアデータ基盤を共創、研究DX・社会実装を加速-",
         "link": "https://example.com/r1", "summary": "", "source": "山陽新聞"},
        {"title": "政府・与党 臨時国会で消費税法案成立を 野党は論戦の構え", "link": "https://example.com/r2",
         "summary": "", "source": "NHK 政治"},
        {"title": "木原官房長官 自民・小野寺氏“消費税減税法案に野党協力を”", "link": "https://example.com/r3",
         "summary": "", "source": "NHK 政治"},
        {"title": "政府 食料品の消費税減税の準備を支援へ 予備費支出も", "link": "https://example.com/r5",
         "summary": "", "source": "NHK 政治"},
        {"title": "物価高で家計の負担増 賃上げは追いつかず", "link": "https://example.com/r4",
         "summary": "", "source": "NHK 経済"},
    ]

    def test_press_release_is_not_picked(self):
        chosen = pick_essays(self.ARTICLES)
        self.assertFalse(any("岡山大学" in a["title"] for a in chosen.values()))

    def test_same_topic_is_not_picked_twice(self):
        chosen = pick_essays(self.ARTICLES)
        self.assertEqual(sum("消費税" in a["title"] for a in chosen.values()), 1)

    def test_common_office_names_do_not_merge_topics(self):
        from ronbun_news.picker import same_topic
        self.assertFalse(same_topic("官房長官 少子化対策を説明", "官房長官 原発再稼働に言及"))
        self.assertTrue(same_topic("臨時国会で消費税法案成立を", "食料品の消費税減税の準備を支援へ"))


if __name__ == "__main__":
    unittest.main()
