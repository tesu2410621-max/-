"""使い方: python -m ronbun_news [--date YYYY-MM-DD] [--out docs]
           [--feed-file ja.xml] [--english-feed-file en.xml]   # テスト用にローカルのRSSを使う
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from .enrich import enrich
from .exam import in_window, season
from .feeds import ENGLISH_FEEDS, FEEDS, fetch_all, parse_feed
from .picker import pick_english, pick_essays
from .render import archive_page, day_page
from .themes import FACULTIES

JST = datetime.timezone(datetime.timedelta(hours=9))
REVIEW_MESSAGE = "ここからは総仕上げ 🔥 出題圏内のニュースを1本ずつ「自分の言葉で説明できる」状態にしよう。"


def load_history(data_dir):
    entries = []
    for path in sorted(data_dir.glob("*.json"), reverse=True):
        entries.append((path.stem, json.loads(path.read_text(encoding="utf-8"))))
    return entries


def _load(files, feeds, label):
    if files:
        return [a for f in files for a in parse_feed(Path(f).read_bytes(), label)]
    return fetch_all(feeds)


def review_picks(day, history):
    """出題圏内に集めた記事から、直近30日に復習していないものを学部ごと・英語2本選ぶ。"""
    recent = {a["link"] for d, e in history[:30] if e.get("mode") == "review"
              for a in e["essays"] + e["english"]}
    pool_essays, pool_english = [], []
    for d, e in history:
        if e.get("mode") == "review" or not in_window(d, day):
            continue
        pool_essays += [{**a, "from_date": d} for a in e["essays"] if a["link"] not in recent]
        pool_english += [{**a, "from_date": d} for a in e["english"] if a["link"] not in recent]
    essays = {}
    for fac in (f["id"] for f in FACULTIES):
        cands = sorted((a for a in pool_essays if a["faculty"] == fac), key=lambda a: a["score"], reverse=True)
        if cands:
            essays[fac] = cands[0]
    english, used = [], set()
    for a in sorted(pool_english, key=lambda a: a["score"], reverse=True):
        if a["theme"] not in used:
            english.append(a)
            used.add(a["theme"])
        if len(english) == 2:
            break
    return essays, english


def build(day, history, ja_articles, en_articles):
    mode = season(day)[0]
    recent_titles = [a["title"] for _, e in history[:7] for a in e["essays"] + e["english"]]
    essays, english, message = {}, [], None

    if mode == "review":
        essays, english = review_picks(day, history)
        message = REVIEW_MESSAGE

    # 生の記事を使うのは、出題圏内の時期か、復習用のストックが足りないときだけ
    missing = [f["id"] for f in FACULTIES if f["id"] not in essays]
    fresh_essays = pick_essays(ja_articles(), missing, recent_titles) if missing else {}
    fresh_english = pick_english(en_articles(), 2 - len(english), recent_titles) if len(english) < 2 else []
    fresh_order = list(fresh_essays)
    enriched_essays, enriched_english, fresh_message, _ = enrich(list(fresh_essays.values()), fresh_english)
    for fac, a in zip(fresh_order, enriched_essays):
        essays[fac] = {**a, "outside_window": mode == "review"}
    english += [{**a, "outside_window": mode == "review"} for a in enriched_english]

    ordered = [essays[f["id"]] for f in FACULTIES if f["id"] in essays]
    if not ordered and not english:
        return None
    # メイン設問は学部を日替わりで回す（4日で一巡）
    rotation = [f["id"] for f in FACULTIES]
    main = next((rotation[(day.toordinal() + k) % 4] for k in range(4)
                 if rotation[(day.toordinal() + k) % 4] in essays), None)
    return {"date": day.isoformat(), "mode": mode, "main": main, "essays": ordered,
            "english": english, "daily_message": message or fresh_message}


def main(argv=None):
    parser = argparse.ArgumentParser(description="慶應入試向けの朝ニュースページを生成する")
    parser.add_argument("--date", default=datetime.datetime.now(JST).date().isoformat())
    parser.add_argument("--out", default="docs")
    parser.add_argument("--feed-file", action="append", help="日本語RSSの代わりに使うローカルファイル（テスト用）")
    parser.add_argument("--english-feed-file", action="append", help="英語RSSの代わりに使うローカルファイル（テスト用）")
    args = parser.parse_args(argv)

    day = datetime.date.fromisoformat(args.date)
    out = Path(args.out)
    data_dir = out / "data"
    (out / "days").mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    history = [(d, e) for d, e in load_history(data_dir) if d != args.date]

    entry = build(day, history,
                  lambda: _load(args.feed_file, FEEDS, "サンプル"),
                  lambda: _load(args.english_feed_file, ENGLISH_FEEDS, "Sample"))
    if entry is None:
        print("[error] 記事を選べませんでした。前日のページを残して終了します。", file=sys.stderr)
        return 1

    (data_dir / f"{args.date}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "days" / f"{args.date}.html").write_text(day_page(entry, base="../"), encoding="utf-8")
    history = sorted(history + [(args.date, entry)], reverse=True)
    (out / "index.html").write_text(day_page(history[0][1]), encoding="utf-8")
    (out / "archive.html").write_text(archive_page(history), encoding="utf-8")
    (out / ".nojekyll").touch()

    for a in entry["essays"]:
        print(f"- [{a['faculty']}/{a['theme']}] {a['title']}", file=sys.stderr)
    for a in entry["english"]:
        print(f"- [EN/{a['theme']}] {a['title']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
