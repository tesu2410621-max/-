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
from .themes import THEME_BY_ID

JST = datetime.timezone(datetime.timedelta(hours=9))
# 小論文面の2枠は、4学部を2日で一巡するように回す（例: 総合政策＋環境情報 → 法＋文 → …）
ROTATION = ["sogo", "hou", "kankyo", "bun"]


def essay_slots(day):
    k = day.toordinal() % 4
    return [ROTATION[k], ROTATION[(k + 2) % 4]]


def load_history(data_dir):
    entries = []
    for path in sorted(data_dir.glob("*.json"), reverse=True):
        entries.append((path.stem, json.loads(path.read_text(encoding="utf-8"))))
    return entries


def _load(files, feeds, label):
    if files:
        return [a for f in files for a in parse_feed(Path(f).read_bytes(), label)]
    return fetch_all(feeds)


def _with_faculties(article):
    """対象学部の表示用に、主対象＋テーマのもう1学部を並べる（例: 総合政策・環境情報）。"""
    others = [f for f in THEME_BY_ID[article["theme"]]["faculties"] if f != article["faculty"]]
    return {**article, "faculties": [article["faculty"]] + others[:1]}


def review_picks(day, history, slots):
    """出題圏内に集めた記事から、直近30日に復習していないものを選ぶ。紙面ごと再利用する。"""
    recent = {a["link"] for d, e in history[:30] if e.get("mode") == "review"
              for a in e["essays"] + e["english"]}
    pool_essays, pool_english = [], []
    for d, e in history:
        if e.get("mode") == "review" or not in_window(d, day):
            continue
        pool_essays += [({**a, "from_date": d}, e) for a in e["essays"] if a["link"] not in recent]
        pool_english += [{**a, "from_date": d} for a in e["english"] if a["link"] not in recent]
    essays, source = {}, None
    for fac in slots:
        cands = sorted((x for x in pool_essays if x[0]["faculty"] == fac), key=lambda x: x[0]["score"], reverse=True)
        if cands:
            essays[fac] = cands[0][0]
            source = source or cands[0][1]
    english, used = [], set()
    for a in sorted(pool_english, key=lambda a: a["score"], reverse=True):
        if a["theme"] not in used:
            english.append(a)
            used.add(a["theme"])
        if len(english) == 2:
            break
    return essays, english, source


def build(day, history, ja_articles, en_articles):
    mode = season(day)[0]
    slots = essay_slots(day)
    recent_titles = [a["title"] for _, e in history[:7] for a in e["essays"] + e["english"]]
    essays, english, source = {}, [], None

    if mode == "review":
        essays, english, source = review_picks(day, history, slots)

    # 生の記事を使うのは、出題圏内の時期か、復習用のストックが足りないときだけ
    missing = [f for f in slots if f not in essays]
    en_raw = en_articles() if missing or len(english) < 2 else []
    fresh_essays = pick_essays(ja_articles(), missing, recent_titles, en_articles=en_raw) if missing else {}
    # 小論文面に使った英文記事は、英語長文面では使わない
    used_links = {a["link"] for a in fresh_essays.values()}
    en_rest = [a for a in en_raw if a["link"] not in used_links]
    fresh_english = pick_english(en_rest, 2 - len(english), recent_titles) if len(english) < 2 else []
    order = list(fresh_essays)
    papers_e, papers_en, theme, history_window, by = enrich(
        [_with_faculties(fresh_essays[f]) for f in order], fresh_english)
    for fac, a in zip(order, papers_e):
        essays[fac] = {**a, "outside_window": mode == "review"}
    english += [{**a, "outside_window": mode == "review"} for a in papers_en]

    ordered = [essays[f] for f in slots if f in essays]
    if not ordered and not english:
        return None
    if source:  # 復習日は、元の号のテーマと世界史の窓を使う
        theme, history_window, by = source["theme"], source["history"], source.get("generated_by", by)
    return {"date": day.isoformat(), "mode": mode, "issue": len(history) + 1, "theme": theme,
            "essays": ordered, "english": english, "history": history_window, "generated_by": by}


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
        print(f"- [{'/'.join(a['faculties'])}:{a['theme']}] {a['title']}", file=sys.stderr)
    for a in entry["english"]:
        print(f"- [EN/{a['theme']}] {a['title']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
