"""日ごとのページ・トップページ・アーカイブのHTMLを生成する。"""

import datetime
from html import escape

from .themes import THEME_BY_ID

WEEKDAYS = "月火水木金土日"

CSS = """
:root{--bg:#f6f5f1;--card:#fff;--ink:#1d1d1f;--sub:#5f6368;--line:#e4e2dc;--accent:#0b3d91;
--accent-soft:#e8eefb;--pro:#1e7a46;--pro-soft:#e7f5ec;--con:#b3261e;--con-soft:#fcebea;--gold:#9a6b00;--gold-soft:#fff5dc}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121316;--card:#1c1d21;--ink:#ececf0;
--sub:#a4a6ad;--line:#2e3036;--accent:#8fb2ff;--accent-soft:#1d2740;--pro:#6fd39a;--pro-soft:#15291e;--con:#ff8a80;
--con-soft:#331a19;--gold:#f3c562;--gold-soft:#2e2612}}
:root[data-theme="dark"]{--bg:#121316;--card:#1c1d21;--ink:#ececf0;--sub:#a4a6ad;--line:#2e3036;--accent:#8fb2ff;
--accent-soft:#1d2740;--pro:#6fd39a;--pro-soft:#15291e;--con:#ff8a80;--con-soft:#331a19;--gold:#f3c562;--gold-soft:#2e2612}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 "Hiragino Sans","Noto Sans JP","Yu Gothic UI",system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--accent)}
header h1{font-size:1.35rem;margin:0}
header .date{color:var(--sub);margin:2px 0 12px}
.msg{background:var(--gold-soft);color:var(--ink);border-left:4px solid var(--gold);padding:10px 14px;border-radius:8px}
.nav{display:flex;gap:16px;font-size:.9rem;margin:10px 0 0}
h2{font-size:1.05rem;margin:32px 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:0 0 16px}
.card.main{border:2px solid var(--accent)}
.chip{display:inline-block;background:var(--accent-soft);color:var(--accent);font-size:.8rem;font-weight:600;
padding:2px 10px;border-radius:999px;margin-right:6px}
.card h3{font-size:1.08rem;line-height:1.5;margin:10px 0 4px}
.card h3 a{color:var(--ink);text-decoration:none}
.card h3 a:hover{text-decoration:underline}
.src{color:var(--sub);font-size:.82rem;margin:0 0 10px}
.label{font-weight:700;font-size:.85rem;color:var(--sub);margin:14px 0 4px}
.sides{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media (max-width:560px){.sides{grid-template-columns:1fr}}
.side{border-radius:10px;padding:10px 12px;font-size:.92rem}
.side.pro{background:var(--pro-soft)}.side.con{background:var(--con-soft)}
.side b{display:block;font-size:.82rem}.side.pro b{color:var(--pro)}.side.con b{color:var(--con)}
.side ul{margin:4px 0 0;padding-left:1.1em}
.concepts span{display:inline-block;border:1px solid var(--line);border-radius:6px;padding:1px 8px;margin:0 6px 6px 0;font-size:.85rem}
.q{background:var(--accent-soft);border-radius:10px;padding:10px 12px;font-weight:600}
ol.outline{margin:6px 0 0;padding-left:1.3em;font-size:.93rem}
details summary{cursor:pointer;color:var(--accent);font-size:.9rem;margin-top:12px}
textarea{width:100%;min-height:180px;margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:10px;
background:var(--bg);color:var(--ink);font:inherit;resize:vertical}
.count{text-align:right;color:var(--sub);font-size:.82rem}
.done{display:flex;align-items:center;gap:8px;margin-top:12px;font-size:.9rem;color:var(--sub)}
.done input{width:18px;height:18px}
.stats{display:flex;gap:10px;margin:14px 0 0}
.stat{flex:1;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 12px;text-align:center}
.stat b{display:block;font-size:1.3rem}.stat span{font-size:.78rem;color:var(--sub)}
.routine{font-size:.92rem}.routine li{margin-bottom:4px}
.archive a{display:block;padding:10px 0;border-bottom:1px solid var(--line);text-decoration:none;color:var(--ink)}
.archive small{color:var(--sub)}
footer{color:var(--sub);font-size:.8rem;margin-top:40px}
"""

SCRIPT = """
(function(){
  var day = document.body.dataset.day;
  function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function set(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  var box = document.getElementById('answer'), counter = document.getElementById('count');
  if (box) {
    box.value = get('answer:'+day) || '';
    var update = function(){ counter.textContent = box.value.replace(/\\s/g,'').length + ' 字'; };
    box.addEventListener('input', function(){ set('answer:'+day, box.value); update(); });
    update();
  }
  document.querySelectorAll('input[data-read]').forEach(function(cb){
    var key = 'read:'+day+':'+cb.dataset.read;
    cb.checked = get(key) === '1';
    cb.addEventListener('change', function(){ set(key, cb.checked ? '1' : '0'); refresh(); });
  });
  function refresh(){
    var days = {}, total = 0;
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k.indexOf('read:') === 0 && localStorage.getItem(k) === '1') { days[k.split(':')[1]] = 1; total++; }
      }
    } catch(e) {}
    var streak = 0, d = new Date(day + 'T00:00:00');
    function key(x){ return x.getFullYear()+'-'+('0'+(x.getMonth()+1)).slice(-2)+'-'+('0'+x.getDate()).slice(-2); }
    while (days[key(d)]) { streak++; d.setDate(d.getDate()-1); }
    var s = document.getElementById('streak'), t = document.getElementById('total');
    if (s) s.textContent = streak; if (t) t.textContent = total;
  }
  refresh();
})();
"""


def _head(title):
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📰</text></svg>">
<style>{CSS}</style></head>"""


def jp_date(day):
    y, m, d = (int(x) for x in day.split("-"))
    wd = WEEKDAYS[datetime.date(y, m, d).weekday()]
    return f"{y}年{m}月{d}日（{wd}）"


def _list(items):
    return "".join(f"<li>{escape(i)}</li>" for i in items)


def _card(i, article, notes, is_main):
    theme = THEME_BY_ID[article["theme"]]
    concepts = "".join(f"<span>{escape(c)}</span>" for c in notes["concepts"])
    outline = f'<ol class="outline">{_list(notes["outline"])}</ol>'
    if is_main:
        task = f"""<p class="label">✍️ 今日のメイン設問</p>
<p class="q">{escape(notes["question"])}</p>
<p class="label">🧭 構成メモ</p>{outline}
<p class="label">📝 答案メモ（この端末に自動保存）</p>
<textarea id="answer" placeholder="まずは構成メモを埋める → 余裕があれば400字で書いてみよう"></textarea>
<div class="count" id="count">0 字</div>"""
    else:
        task = f"""<details><summary>✍️ 設問と構成メモを見る</summary>
<p class="q">{escape(notes["question"])}</p>{outline}</details>"""
    return f"""<article class="card{' main' if is_main else ''}">
<span class="chip">{theme['emoji']} {escape(theme['name'])}</span>
<h3><a href="{escape(article['link'])}" target="_blank" rel="noopener">{escape(article['title'])}</a></h3>
<p class="src">{escape(article['source'])}</p>
<p>{escape(notes['summary'])}</p>
<p class="label">💡 小論文でのポイント</p><p>{escape(notes['why_it_matters'])}</p>
<p class="label">⚖️ 論点</p>
<div class="sides"><div class="side pro"><b>推進・賛成の論拠</b><ul>{_list(notes['pros'])}</ul></div>
<div class="side con"><b>慎重・反対の論拠</b><ul>{_list(notes['cons'])}</ul></div></div>
<p class="label">🔑 使える概念</p><div class="concepts">{concepts}</div>
{task}
<label class="done"><input type="checkbox" data-read="{i}"> 読んで論点を1つ言えるようになった</label>
</article>"""


def day_page(day, data, base=""):
    articles, notes = data["articles"], data["notes"]
    main_i = notes["main_index"]
    cards_main = _card(main_i, articles[main_i], notes["articles"][main_i], True)
    cards_rest = "".join(_card(i, a, notes["articles"][i], False)
                         for i, a in enumerate(articles) if i != main_i)
    by = "Claude による解説" if notes.get("generated_by") == "claude" else "テンプレート解説"
    return f"""{_head(f"慶應小論文 朝ニュース {day}")}
<body data-day="{day}"><main>
<header><h1>📰 慶應小論文 朝のニュース</h1>
<p class="date">{jp_date(day)}　総合政策学部・併願対策</p>
<p class="msg">{escape(notes['daily_message'])}</p>
<div class="stats"><div class="stat"><b id="streak">0</b><span>🔥 連続日数</span></div>
<div class="stat"><b id="total">0</b><span>📚 読んだ記事</span></div></div>
<nav class="nav"><a href="{base}index.html">今日</a><a href="{base}archive.html">過去のニュース</a></nav></header>
<h2>🎯 今日じっくり考える1本</h2>{cards_main}
<h2>📚 そのほかの注目ニュース</h2>{cards_rest}
<section class="card routine"><b>⏱ 朝のルーティン（10分）</b><ol>
<li>全記事の見出しと「論点」だけ読む（3分）</li>
<li>メイン設問の構成メモ4行を埋める（5分）</li>
<li>「使える概念」から1つ選び、自分の言葉で説明できるか確認（2分）</li>
</ol>週末はメイン設問から1本選び、時間を計って800字で書こう 💪</section>
<footer>記事の見出し・概要は各配信元のRSSより。本文は必ずリンク先で確認してください。解説：{by}</footer>
</main><script>{SCRIPT}</script></body></html>"""


def archive_page(entries):
    rows = []
    for day, data in entries:
        themes = " ".join(THEME_BY_ID[a["theme"]]["emoji"] for a in data["articles"])
        main = data["articles"][data["notes"]["main_index"]]["title"]
        rows.append(f'<a href="days/{day}.html"><b>{jp_date(day)}</b> {themes}<br><small>{escape(main)}</small></a>')
    return f"""{_head("慶應小論文 朝ニュース アーカイブ")}
<body><main><header><h1>📚 過去のニュース</h1>
<nav class="nav"><a href="index.html">今日のニュースへ</a></nav></header>
<section class="card archive">{''.join(rows) or '<p>まだありません</p>'}</section>
</main></body></html>"""
