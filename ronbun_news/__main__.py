"""使い方: python -m ronbun_news [--date YYYY-MM-DD] [--out docs] [--feed-file sample.xml]"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from .enrich import enrich
from .feeds import fetch_all, parse_feed
from .picker import pick
from .render import archive_page, day_page

JST = datetime.timezone(datetime.timedelta(hours=9))


def load_history(data_dir):
    entries = []
    for path in sorted(data_dir.glob("*.json"), reverse=True):
        entries.append((path.stem, json.loads(path.read_text(encoding="utf-8"))))
    return entries


def main(argv=None):
    parser = argparse.ArgumentParser(description="慶應小論文向けの朝ニュースページを生成する")
    parser.add_argument("--date", default=datetime.datetime.now(JST).date().isoformat())
    parser.add_argument("--out", default="docs")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--feed-file", action="append",
                        help="ネットから取らずにローカルのRSSファイルを使う（テスト用）")
    args = parser.parse_args(argv)

    out = Path(args.out)
    data_dir = out / "data"
    (out / "days").mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    history = [(d, e) for d, e in load_history(data_dir) if d != args.date]
    recent_titles = [a["title"] for _, e in history[:7] for a in e["articles"]]

    if args.feed_file:
        raw = [a for f in args.feed_file for a in parse_feed(Path(f).read_bytes(), "サンプル")]
    else:
        raw = fetch_all()
    print(f"取得した記事: {len(raw)} 件", file=sys.stderr)

    articles = pick(raw, n=args.count, exclude_titles=recent_titles)
    if not articles:
        print("[error] 小論文向けの記事を選べませんでした。前日のページを残して終了します。", file=sys.stderr)
        return 1

    entry = {"date": args.date, "articles": articles, "notes": enrich(articles)}
    (data_dir / f"{args.date}.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")

    (out / "days" / f"{args.date}.html").write_text(day_page(args.date, entry, base="../"), encoding="utf-8")
    history = sorted(history + [(args.date, entry)], reverse=True)
    latest_day, latest = history[0]
    (out / "index.html").write_text(day_page(latest_day, latest), encoding="utf-8")
    (out / "archive.html").write_text(archive_page(history), encoding="utf-8")
    (out / ".nojekyll").touch()

    for a in articles:
        print(f"- [{a['theme']}] {a['title']} (score {a['score']:.1f})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
