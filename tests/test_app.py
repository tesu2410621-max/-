import datetime
import json
import tempfile
import unittest
from pathlib import Path

from ronbun_news.__main__ import build, main
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
        self.assertEqual([a["faculty"] for a in entry["essays"]], ["bun", "hou", "kankyo", "sogo"])
        self.assertEqual(len(entry["english"]), 2)
        self.assertIn(entry["main"], {"bun", "hou", "kankyo", "sogo"})

    def test_main_faculty_rotates(self):
        mains = {build(D(2026, 10, d), [], ja, en)["main"] for d in range(1, 5)}
        self.assertEqual(mains, {"bun", "hou", "kankyo", "sogo"})

    def test_review_mode_uses_archive_without_repeats(self):
        history = []
        for d in (D(2026, 11, 1), D(2026, 11, 2)):
            history.insert(0, (d.isoformat(), build(d, history, ja, en)))
        dec1 = build(D(2026, 12, 1), history, offline, offline)
        self.assertEqual(dec1["mode"], "review")
        self.assertTrue(all(a.get("from_date") for a in dec1["essays"] + dec1["english"]))
        history.insert(0, ("2026-12-01", dec1))
        dec2 = build(D(2026, 12, 2), history, ja, en)
        seen = {a["link"] for a in dec1["essays"]}
        self.assertFalse(seen & {a["link"] for a in dec2["essays"] if a.get("from_date")})

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
            self.assertEqual(len(data["essays"]), 4)
            index = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn("2026年10月1日（木）", index)
            self.assertIn("出題圏の締め切り", index)
            self.assertIn("英語長文の背景知識", index)
            archive = (root / "archive.html").read_text(encoding="utf-8")
            self.assertLess(archive.index("2026-10-01"), archive.index("2026-09-30"))


if __name__ == "__main__":
    unittest.main()
