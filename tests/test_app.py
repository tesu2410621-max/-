import json
import tempfile
import unittest
from pathlib import Path

from ronbun_news.__main__ import main
from ronbun_news.feeds import parse_feed
from ronbun_news.picker import pick, score

SAMPLE = Path(__file__).with_name("sample_feed.xml")


class PickTest(unittest.TestCase):
    def setUp(self):
        self.articles = parse_feed(SAMPLE.read_bytes(), "サンプル")

    def test_parse(self):
        self.assertEqual(len(self.articles), 9)
        self.assertTrue(self.articles[0]["published"].startswith("2026-09-30"))

    def test_noise_is_excluded(self):
        titles = [a["title"] for a in pick(self.articles, n=10)]
        self.assertFalse(any("野球" in t or "逮捕" in t for t in titles))

    def test_duplicates_and_theme_diversity(self):
        chosen = pick(self.articles, n=5)
        self.assertEqual(len(chosen), 5)
        self.assertEqual(sum("生成AI" in a["title"] for a in chosen), 1)
        self.assertEqual(len({a["theme"] for a in chosen}), 5)

    def test_recent_titles_are_skipped(self):
        chosen = pick(self.articles, n=10, exclude_titles=["【サンプル】出生数が過去最少に　少子化対策の見直し論議"])
        self.assertFalse(any("出生数" in a["title"] for a in chosen))

    def test_ascii_keyword_boundary(self):
        self.assertEqual(score({"title": "EMAIL配信の新機能", "summary": ""})[1], None)


class BuildTest(unittest.TestCase):
    def test_build_site(self):
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(main(["--date", "2026-09-30", "--out", out, "--feed-file", str(SAMPLE)]), 0)
            self.assertEqual(main(["--date", "2026-10-01", "--out", out, "--feed-file", str(SAMPLE)]), 0)
            root = Path(out)
            data = json.loads((root / "data" / "2026-09-30.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data["notes"]["articles"]), len(data["articles"]))
            index = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn("2026年10月1日（木）", index)
            archive = (root / "archive.html").read_text(encoding="utf-8")
            self.assertLess(archive.index("2026-10-01"), archive.index("2026-09-30"))
            self.assertTrue((root / "days" / "2026-09-30.html").exists())


if __name__ == "__main__":
    unittest.main()
