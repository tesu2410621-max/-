"""「慶應入試新聞」の紙面HTML（画面表示とA5印刷の両対応）と、アーカイブを生成する。"""

import datetime
import re
from html import escape

from .exam import banner
from .themes import FACULTY_BY_ID

WEEKDAYS = "月火水木金土日"

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&'
         'family=Noto+Serif+JP:wght@400;700;900&display=swap" rel="stylesheet">')

CSS = """
:root{color-scheme:light;--ink:#1a1a1a;--sub:#555;--rule:#1a1a1a;--line:#bdbdbd;--paper:#fff;--desk:#e9e7e2;--tint:#efeeea}
*{box-sizing:border-box}
html{background:var(--desk)}
body{margin:0;color:var(--ink);background:var(--desk);
font:15px/1.9 "Noto Serif JP","Hiragino Mincho ProN","Yu Mincho",serif}
.sans,.kicker,.sec,.topbar,.dateline,.index,.box h4,.tools,.src,.foot,h3.label,.from,.window,.note{
font-family:"Noto Sans JP","Hiragino Sans","Yu Gothic",sans-serif}
.tools{max-width:760px;margin:0 auto;padding:12px 16px 0;display:flex;gap:16px;font-size:.85rem;flex-wrap:wrap}
.tools a{color:var(--ink)}
.sheet{max-width:760px;margin:12px auto 40px;background:var(--paper);padding:28px 32px 36px;box-shadow:0 1px 3px rgba(0,0,0,.15)}
@media (max-width:600px){.sheet{padding:20px 16px 28px;margin:8px 0 24px}}
.topbar{display:flex;justify-content:space-between;gap:8px;font-size:.72rem;color:var(--sub)}
.masthead{text-align:center;margin:4px 0 0}
.masthead h1{font-weight:900;font-size:clamp(2rem,8vw,3.1rem);letter-spacing:.18em;margin:0;line-height:1.3}
.masthead .en{font-size:.72rem;letter-spacing:.42em;color:var(--sub);margin:2px 0 8px}
.dateline{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;border-top:3px double var(--rule);
border-bottom:1px solid var(--rule);padding:4px 0;font-size:.78rem}
.index{display:flex;border:1px solid var(--rule);margin:12px 0 6px}
.index .v{writing-mode:vertical-rl;background:var(--ink);color:#fff;font-weight:700;font-size:.78rem;padding:8px 4px;letter-spacing:.2em}
.index ol{list-style:none;margin:0;padding:4px 10px;flex:1;font-size:.8rem}
.index li{border-bottom:1px dotted var(--line);padding:3px 0;line-height:1.5}
.index li:last-child{border-bottom:0}
.index b{display:inline-block;min-width:5.2em}
.window{font-size:.74rem;color:var(--sub);margin:0 0 4px}
.sec{display:flex;align-items:center;gap:10px;margin:26px 0 8px}
.sec span{background:var(--ink);color:#fff;font-weight:700;font-size:.8rem;padding:3px 10px;letter-spacing:.1em}
.sec::after{content:"";flex:1;border-top:2px solid var(--rule)}
.kicker{font-size:.76rem;font-weight:700;color:var(--sub);margin:0}
.from{font-size:.74rem;font-weight:700;margin:2px 0 0}
h2.hl{font-weight:900;font-size:clamp(1.45rem,5.2vw,1.9rem);line-height:1.35;margin:2px 0 6px}
.subhead{font-weight:700;font-size:1.02rem;border-left:5px solid var(--ink);padding-left:8px;margin:0 0 8px;line-height:1.5}
.lead{font-family:"Noto Sans JP","Hiragino Sans",sans-serif;font-weight:700;font-size:.9rem;border-top:1px solid var(--rule);
border-bottom:1px solid var(--rule);padding:8px 0;margin:0 0 4px;line-height:1.8}
.lead .src{font-weight:400;font-size:.76rem;color:var(--sub)}
h3.label{font-size:.88rem;font-weight:700;border-bottom:1px solid var(--rule);padding-bottom:2px;margin:16px 0 6px}
p.body{text-indent:1em;margin:0 0 6px}
b.k{font-weight:700;text-decoration:underline;text-decoration-thickness:1.5px;text-underline-offset:3px}
ul.dots{list-style:none;padding:0;margin:6px 0}
ul.dots li{padding-left:1em;text-indent:-1em}
ul.dots li::before{content:"・"}
.box{border:1px solid var(--rule);padding:8px 12px;margin:12px 0}
.box h4{font-size:.8rem;margin:0 0 6px;padding-bottom:3px;border-bottom:1px solid var(--line)}
.issue .cols{display:grid;grid-template-columns:1fr 1fr}
.issue .cols>div{padding:0 10px}.issue .cols>div:first-child{border-right:1px solid var(--line);padding-left:0}
.issue .cols b{font-family:"Noto Sans JP",sans-serif;font-size:.8rem}
.issue ul{margin:2px 0 0}
.kw{background:var(--tint);border:0;border-left:4px solid var(--ink)}
.kw p{margin:2px 0;font-size:.9rem}
.q{border:1.5px dashed var(--ink)}
.ans{background:var(--tint);border-left:0;border-right:0;border-width:1.5px 0}
.ans p{margin:2px 0;font-size:.9rem}
.ans b,.kw b{font-family:"Noto Sans JP",sans-serif}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media (max-width:600px){.pair,.issue .cols{grid-template-columns:1fr}.issue .cols>div{padding:0!important;border:0!important}}
table.words{width:100%;border-collapse:collapse;font-size:.88rem}
table.words td{border-bottom:1px dotted var(--line);padding:3px 4px}
table.words td:first-child{font-style:italic;font-weight:700;font-family:Georgia,"Times New Roman",serif}
.ex .en{font-style:italic;font-family:Georgia,"Times New Roman",serif;font-size:.98rem;margin:0;line-height:1.6}
.ex .ja{font-size:.78rem;color:var(--sub);margin:2px 0 0}
.hist{border:1px solid var(--rule);margin:26px 0 8px}
.hist .bar{background:var(--ink);color:#fff;font-family:"Noto Sans JP",sans-serif;font-weight:700;padding:3px 10px;letter-spacing:.3em;font-size:.85rem}
.hist .in{padding:8px 12px}
.note{font-size:.78rem;color:var(--sub);border:1px solid var(--line);padding:6px 10px;margin:10px 0}
.foot{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;border-top:1px solid var(--rule);
margin-top:14px;padding-top:4px;font-size:.7rem;color:var(--sub)}
.archive a{display:block;padding:10px 0;border-bottom:1px dotted var(--line);color:var(--ink);text-decoration:none}
.archive small{color:var(--sub)}
@page{size:A5;margin:10mm 10mm 11mm}
@media print{
  html,body{background:#fff}
  body{font-size:9.2pt;line-height:1.68}
  .tools,.lead a{display:none}
  .sheet{max-width:none;margin:0;padding:0;box-shadow:none}
  .masthead h1{font-size:30pt}
  .masthead .en{margin:0 0 4px}
  .index{margin:8px 0 4px}.index ol{font-size:8pt}.index li{padding:1px 0;line-height:1.45}
  .sec{margin:10px 0 4px}
  h2.hl{font-size:17pt;margin:0 0 4px}
  .subhead{font-size:10pt;margin:0 0 6px}
  .lead{font-size:8.8pt;padding:5px 0;line-height:1.65}
  h3.label{font-size:8.8pt;margin:9px 0 4px}
  .box{margin:8px 0;padding:6px 10px}
  .kw p,.ans p{font-size:8.8pt}
  table.words{font-size:8.4pt}
  table.words td{padding:2px 4px;white-space:nowrap}
  .newpage{break-before:page}
  .box,.ex,.hist{break-inside:avoid}
  h2.hl,.subhead,h3.label,.sec,.kicker{break-after:avoid}
  a{color:inherit;text-decoration:none}
}
"""


def jp_date(day):
    y, m, d = (int(x) for x in day.split("-"))
    wd = WEEKDAYS[datetime.date(y, m, d).weekday()]
    return f"{y}年（令和{y - 2018}年）{m}月{d}日　{wd}曜日"


def short_date(day):
    _, m, d = (int(x) for x in day.split("-"))
    return f"{m}月{d}日"


def t(text):
    """エスケープしたうえで **重要語** を下線付きの太字にする。"""
    return re.sub(r"\*\*(.+?)\*\*", r'<b class="k">\1</b>', escape(text or ""))


def plain(text):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")


def _dots(items):
    items = [i for i in items if i]
    return f'<ul class="dots">{"".join(f"<li>{t(i)}</li>" for i in items)}</ul>' if items else ""


def _head(title):
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📰</text></svg>">
{FONTS}<style>{CSS}</style></head>"""


def faculty_label(a):
    """例: 総合政策・環境情報／法学部・総合政策（1文字の学部名だけ「学部」を残す）"""
    names = [FACULTY_BY_ID[f]["name"] for f in a.get("faculties") or [a["faculty"]]]
    return "・".join(n if len(n.removesuffix("学部")) == 1 else n.removesuffix("学部") for n in names)


def _origin(a):
    if a.get("from_date"):
        return f'<p class="from">【復習】{short_date(a["from_date"])}の記事（出題圏内）</p>'
    if a.get("outside_window"):
        return '<p class="from">【参考】出題圏外の新しいニュース。テーマ理解用として読もう</p>'
    return ""


def _lead(p, link):
    src = f'<span class="src">（{escape(p["sources"])}）</span>' if p.get("sources") else ""
    return (f'<p class="lead">{t(p["lead"])}{src} '
            f'<a class="src" href="{escape(link)}" target="_blank" rel="noopener">元記事</a></p>')


def _top(label, kicker, a):
    p = a["paper"]
    return (f'<div class="sec"><span>{label}</span></div><p class="kicker">{escape(kicker)}</p>{_origin(a)}'
            f'<h2 class="hl">{t(p["headline"])}</h2>'
            + (f'<p class="subhead">{t(p["subhead"])}</p>' if p.get("subhead") else "")
            + _lead(p, a["link"])
            + (f'<h3 class="label">何が起きたか</h3><p class="body">{t(p["what_happened"])}</p>'
               if p.get("what_happened") else ""))


def essay_section(a, first):
    p = a["paper"]
    parts = [f'<section class="{"" if first else "newpage"}">', _top("小論文面", faculty_label(a), a)]
    if p.get("context"):
        parts.append(f'<h3 class="label">{escape(p["context_title"])}</h3>'
                     + "".join(f'<p class="body">{t(x)}</p>' for x in p["context"].split("\n") if x.strip()))
    parts.append(_dots(p.get("points", [])))
    parts.append(f'<div class="box issue"><h4>論点　{t(p["issue"])}</h4><div class="cols">'
                 f'<div><b>【賛成】</b>{_dots(p["pros"])}</div><div><b>【反対・慎重】</b>{_dots(p["cons"])}</div></div></div>')
    if p.get("connection"):
        parts.append(f'<h3 class="label">学部とのつながり</h3><p class="body">{t(p["connection"])}</p>')
    kws = "".join(f'<p><b>{escape(k["term"])}</b>{"：" + t(k["definition"]) if k["definition"] else ""}</p>'
                  for k in p["keywords"])
    parts.append(f'<div class="box kw"><h4>小論文で使えるキーワード</h4>{kws}</div>')
    parts.append(f'<div class="box q"><h4>1分思考問題</h4><p style="margin:0">{t(p["question"])}</p></div>')
    if p.get("answer_claim"):
        parts.append(f'<div class="box ans"><h4>解答例</h4><p><b>主張：</b>{t(p["answer_claim"])}</p>'
                     f'<p><b>理由：</b>{t(p["answer_reason"])}</p><p><b>具体策：</b>{t(p["answer_plan"])}</p></div>')
    # 解答例の下の余白は、次の面が改ページで始まるので手書き欄として使える
    parts.append("</section>")
    return "".join(parts)


def english_section(a):
    p = a["paper"]
    words = "".join(f'<tr><td>{escape(v["en"])}</td><td>{escape(v["ja"])}</td></tr>' for v in p["vocab"])
    forms = "".join(f'<tr><td>{escape(w["base"])}（{w["base_pos"]}）</td>'
                    f'<td>→ {escape(w["derived"])}（{w["derived_pos"]}）</td></tr>' for w in p.get("word_forms", []))
    tables = f'<div class="box"><h4>単語</h4><table class="words">{words}</table></div>'
    if forms:
        tables = (f'<div class="pair">{tables}<div class="box"><h4>語形変化（名詞化）</h4>'
                  f'<table class="words">{forms}</table></div></div>')
    parts = ['<section class="newpage">', _top("英語長文面", "商学部・経済学部", a),
             f'<h3 class="label">慶應英語で出る考え方</h3><p class="body">{t(p["keio_angle"])}</p>', tables]
    if p.get("example_en"):
        parts.append(f'<div class="box ex"><h4>例文</h4><p class="en">{escape(p["example_en"])}</p>'
                     f'<p class="ja">{escape(p["example_ja"])}</p></div>')
    parts.append("</section>")
    return "".join(parts)


def history_section(h):
    if not h or not h.get("paragraphs"):
        return ""
    body = "".join(f'<p class="body">{t(x)}</p>' for x in h["paragraphs"])
    return f'<section class="hist"><div class="bar">世界史の窓</div><div class="in">{body}</div></section>'


def _texts(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts(v)


def reading_minutes(entry):
    """日本語は1分500字、英語は1分150語として紙面全体を読む時間を見積もる。"""
    ja = en_words = 0
    for x in _texts([a["paper"] for a in entry["essays"] + entry["english"]] + [entry.get("history")]):
        if x.isascii():
            en_words += len(x.split())
        else:
            ja += len(x)
    return max(1, round(ja / 500 + en_words / 150))


def _motto(day):
    m = int(day.split("-")[1])
    season = "秋" if m in (9, 10, 11) else "冬" if m in (12, 1, 2) else "春" if m in (3, 4, 5) else "夏"
    return f"— {season}の一問が、2月の一点に —"


def day_page(entry, base=""):
    day = entry["date"]
    _, window_text = banner(datetime.date.fromisoformat(day))
    marks = "①②③④"
    index = [("小論文" + marks[i], a["paper"]["index_line"]) for i, a in enumerate(entry["essays"])]
    index += [("英語" + marks[i], a["paper"]["index_line"]) for i, a in enumerate(entry["english"])]
    if (entry.get("history") or {}).get("index_line"):
        index.append(("世界史", entry["history"]["index_line"]))
    index_html = "".join(f"<li><b>{escape(k)}</b>{t(v)}</li>" for k, v in index)
    sources = sorted({s.strip() for a in entry["essays"] + entry["english"]
                      for s in re.split(r"[、／/,]", a["paper"].get("sources") or a["source"]) if s.strip()})
    simple = "" if entry.get("generated_by") == "claude" else (
        '<p class="note">※ 簡易版の紙面です（取材・解答例・世界史の窓なし）。'
        'GitHub の Secrets に ANTHROPIC_API_KEY を登録すると、記事を取材したうえで全面を作成します。</p>')
    theme = f"本日のテーマ：{escape(entry['theme'])}" if entry.get("theme") else ""
    return f"""{_head(f"慶應入試新聞 第{entry['issue']}号（{short_date(day)}）")}
<body>
<nav class="tools"><a href="{base}index.html">最新号</a><a href="{base}archive.html">バックナンバー</a>
<a href="{base}pdf/{day}.pdf">📄 PDF（手書き用・A5）</a><a href="#" onclick="window.print();return false">🖨 印刷</a></nav>
<main class="sheet">
<div class="topbar"><span>第{entry['issue']}号</span><span>小論文・英語長文・世界史の背景知識</span><span>毎朝6時配信</span></div>
<header class="masthead"><h1>慶應入試新聞</h1><p class="en">KEIO ENTRANCE EXAM TIMES</p></header>
<div class="dateline"><span>{jp_date(day)}</span><span>{theme}</span><span>約{reading_minutes(entry)}分</span></div>
<div class="index"><div class="v">本日の紙面</div><ol>{index_html}</ol></div>
<p class="window">{escape(window_text)}</p>
{simple}
{"".join(essay_section(a, i == 0) for i, a in enumerate(entry["essays"]))}
{"".join(english_section(a) for a in entry["english"])}
{history_section(entry.get("history"))}
<footer class="foot"><span>出典　{escape("／".join(sources))}</span><span>{_motto(day)}</span></footer>
</main></body></html>"""


def archive_page(entries):
    rows = []
    for day, e in entries:
        tag = "（復習）" if e.get("mode") == "review" else ""
        heads = " ／ ".join(plain((a.get("paper") or {}).get("headline", a["title"])) for a in e.get("essays", []))
        rows.append(f'<a href="days/{day}.html"><b>第{e.get("issue", "")}号　{jp_date(day)}</b>{tag}<br>'
                    f'<small>{escape(e.get("theme", ""))}　{escape(heads)}</small></a>')
    return f"""{_head("慶應入試新聞 バックナンバー")}
<body><nav class="tools"><a href="index.html">最新号</a></nav>
<main class="sheet"><header class="masthead"><h1>慶應入試新聞</h1><p class="en">BACK NUMBERS</p></header>
<section class="archive">{''.join(rows) or '<p>まだありません</p>'}</section></main></body></html>"""
