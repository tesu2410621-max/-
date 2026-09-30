"""ニュースRSSの取得とパース（標準ライブラリのみ）。"""

import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime


def _google_news(query, lang="ja"):
    q = urllib.parse.quote(f"{query} when:1d")
    if lang == "en":
        return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"


# どれかが落ちても他で補えるよう、複数の配信元を使う
FEEDS = [
    ("NHK 社会", "https://www.nhk.or.jp/rss/news/cat1.xml"),
    ("NHK 科学・医療", "https://www.nhk.or.jp/rss/news/cat3.xml"),
    ("NHK 政治", "https://www.nhk.or.jp/rss/news/cat4.xml"),
    ("NHK 経済", "https://www.nhk.or.jp/rss/news/cat5.xml"),
    ("NHK 国際", "https://www.nhk.or.jp/rss/news/cat6.xml"),
    ("Yahoo! 国内", "https://news.yahoo.co.jp/rss/topics/domestic.xml"),
    ("Yahoo! 国際", "https://news.yahoo.co.jp/rss/topics/world.xml"),
    ("Yahoo! 経済", "https://news.yahoo.co.jp/rss/topics/business.xml"),
    ("Yahoo! IT", "https://news.yahoo.co.jp/rss/topics/it.xml"),
    ("Yahoo! 科学", "https://news.yahoo.co.jp/rss/topics/science.xml"),
    ("Google ニュース", _google_news("政策 課題")),
    ("Google ニュース", _google_news("少子化 OR 人口減少 OR 地方創生")),
    ("Google ニュース", _google_news("生成AI 規制 OR 脱炭素 OR 多様性")),
    ("Google ニュース", _google_news("文化 OR 歴史 OR 言語 OR 文学 OR 表現の自由")),
    ("Google ニュース", _google_news("研究 OR 宇宙 OR 遺伝子 OR テクノロジー 社会")),
    ("Google ニュース", _google_news("憲法 OR 裁判 OR 人権 OR 民主主義")),
]

# 英語長文（経済・商学部）の背景知識用。英語のまま読むことで語彙の予習も兼ねる
ENGLISH_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("BBC Science & Environment", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
    ("NPR Technology", "https://feeds.npr.org/1019/rss.xml"),
    ("The Conversation", "https://theconversation.com/global/articles.atom"),
    ("The Guardian Economics", "https://www.theguardian.com/business/economics/rss"),
    ("Google News", _google_news("economy OR inequality OR consumers study", "en")),
    ("Google News", _google_news("psychology study OR behavioral economics OR climate policy", "en")),
]

USER_AGENT = "Mozilla/5.0 (compatible; ronbun-news/1.0)"
TAG_RE = re.compile(r"<[^>]+>")


def clean(text):
    text = html.unescape(TAG_RE.sub("", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_feed(xml_bytes, source):
    """RSS 2.0 / Atom を記事dictのリストにする。"""
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        title = clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        summary = clean(item.findtext("description"))
        pub = item.findtext("pubDate")
        src = item.findtext("source")
        publisher = clean(src) if src else source
        # Google ニュースはタイトル末尾に「 - 媒体名」が付く
        if src and title.endswith(f" - {publisher}"):
            title = title[: -len(f" - {publisher}")]
        if summary == title or summary.startswith(title):
            summary = ""
        items.append({
            "title": title,
            "link": link,
            "summary": summary[:300],
            "source": publisher,
            "published": _iso(pub),
        })
    atom = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{atom}entry"):
        link_el = entry.find(f"{atom}link")
        items.append({
            "title": clean(entry.findtext(f"{atom}title")),
            "link": link_el.get("href", "") if link_el is not None else "",
            "summary": clean(entry.findtext(f"{atom}summary"))[:300],
            "source": source,
            "published": entry.findtext(f"{atom}updated") or "",
        })
    return [i for i in items if i["title"] and i["link"]]


def _iso(pub):
    if not pub:
        return ""
    try:
        return parsedate_to_datetime(pub).isoformat()
    except (TypeError, ValueError):
        return ""


def fetch_all(feeds=FEEDS, timeout=20):
    articles = []
    for source, url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                got = parse_feed(resp.read(), source)
            articles.extend(got)
            print(f"[info] {source}: {len(got)} 件", file=sys.stderr)
        except Exception as e:  # 1つの配信元の失敗で全体を止めない
            print(f"[warn] {source} の取得に失敗: {e}", file=sys.stderr)
    return articles
