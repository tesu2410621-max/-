"""選んだ記事から「慶應入試新聞」の紙面を書く。

ANTHROPIC_API_KEY があれば、Claude が
  1. Web検索・Web取得で記事の事実関係（数字・固有名詞・出典）を調べ、
  2. その取材メモだけを根拠に、紙面（小論文面・英語長文面・世界史の窓）を書く。
キーが無い場合や失敗した場合は、テーマ定義から作る簡易版の紙面にする。
紙面は記事 dict の "paper" に入れて返す（復習モードでそのまま再利用するため）。
"""

import json
import os
import sys

from .themes import ENGLISH_THEME_BY_ID, FACULTY_BY_ID, THEME_BY_ID

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_CONTINUATIONS = 5

RESEARCH_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 8},
]

RESEARCH_SYSTEM = """あなたは受験新聞の取材記者です。渡されたニュースそれぞれについて、
記事のリンク先を web_fetch で読むか、見出しで web_search して、事実関係を確認してください。

各記事について、次を日本語の箇条書きで取材メモにまとめる:
- いつ・誰が・何をしたか（日付、組織名、人名）
- 規模を示す数字（金額、人数、割合など）と、その数字の出典媒体名
- 背景・経緯（なぜ起きたか、これまでの流れ）
- 賛否や懸念など、議論になっている点
確認できなかったことは「未確認」と書き、推測で埋めないこと。最後に取材メモだけを出力する。"""

WRITER_SYSTEM = """あなたは慶應義塾大学の入試対策を指導するプロの受験コーチであり、受験新聞「慶應入試新聞」の編集者です。
読者は高校3年生。毎朝【合計10分】で読み切れる紙面を書きます。

紙面の構成:
- 小論文面（2本）：指定された学部（文学部・法学部・環境情報学部・総合政策学部）の小論文で使える形に解説する。
- 英語長文面（2本）：慶應の経済学部・商学部の英語長文を読むための背景知識と語彙。商学部で出る語形変化（特に名詞化）も扱う。
- 世界史の窓：今日のテーマに関わる世界史の出来事。慶應商学部の世界史で問われうる経済史・社会史を中心に。

厳守すること:
- 事実（数字・固有名詞・日付）は取材メモに書かれたものだけを使う。メモに無いことは書かない。「未確認」の事柄は書かない。
- 世界史の年号・人名は教科書レベルで確実なものだけを使う。
- 賛否は必ず両側を示し、どちらの立場でも書けるようにする。
- 本文中の重要語は **語** のように ** で囲む（1段落に1〜2個まで）。
- 高校生にわかる言葉で、1文を短く。絵文字は使わない。
- 各フィールドの字数目安を守り、全体で10分に収める。"""

ESSAY_SCHEMA = {
    "type": "object",
    "properties": {
        "index_line": {"type": "string", "description": "本日の紙面に載せる1行（例: 豪州、石炭火力の跡地に巨大蓄電池 — 脱炭素と地域の「公正な移行」）40字以内"},
        "headline": {"type": "string", "description": "見出し（20字以内）"},
        "subhead": {"type": "string", "description": "袖見出し（40字以内）"},
        "lead": {"type": "string", "description": "リード文。事実のみ（130字以内）"},
        "sources": {"type": "string", "description": "リード文の出典媒体名（例: AP通信、AFP／Malay Mail）"},
        "what_happened": {"type": "string", "description": "何が起きたか（150字程度）"},
        "context_title": {"type": "string", "enum": ["なぜ重要か", "背景"]},
        "context": {"type": "string", "description": "なぜ重要か／背景（200字程度）"},
        "points": {"type": "array", "items": {"type": "string"}, "description": "補足の箇条書き（1〜2個、各50字以内）"},
        "issue": {"type": "string", "description": "論点の問い（例: 脱炭素のため、石炭火力の廃止を急ぐべきか）30字以内"},
        "pros": {"type": "array", "items": {"type": "string"}, "description": "賛成の論拠（2個、各30字以内）"},
        "cons": {"type": "array", "items": {"type": "string"}, "description": "反対・慎重の論拠（2個、各30字以内）"},
        "connection": {"type": "string", "description": "学部とのつながり。指定学部でどう出題されうるか（120字程度）"},
        "keywords": {
            "type": "array",
            "description": "小論文で使えるキーワード（4個）",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "definition": {"type": "string", "description": "40字以内"}},
                "required": ["term", "definition"],
                "additionalProperties": False,
            },
        },
        "question": {"type": "string", "description": "1分思考問題（80字以内）"},
        "answer_claim": {"type": "string", "description": "解答例の主張（60字以内）"},
        "answer_reason": {"type": "string", "description": "解答例の理由（80字以内）"},
        "answer_plan": {"type": "string", "description": "解答例の具体策（80字以内）"},
    },
    "required": ["index_line", "headline", "subhead", "lead", "sources", "what_happened", "context_title",
                 "context", "points", "issue", "pros", "cons", "connection", "keywords", "question",
                 "answer_claim", "answer_reason", "answer_plan"],
    "additionalProperties": False,
}

ENGLISH_SCHEMA = {
    "type": "object",
    "properties": {
        "index_line": {"type": "string", "description": "本日の紙面に載せる1行（40字以内）"},
        "headline": {"type": "string", "description": "日本語の見出し（20字以内）"},
        "subhead": {"type": "string", "description": "袖見出し（40字以内）"},
        "lead": {"type": "string", "description": "リード文。事実のみ（130字以内）"},
        "sources": {"type": "string", "description": "出典媒体名"},
        "what_happened": {"type": "string", "description": "何が起きたか（120字程度）"},
        "keio_angle": {"type": "string", "description": "慶應英語で出る考え方。経済・経営の概念で読み解き、英文で出やすい表現を示す（220字程度）"},
        "vocab": {
            "type": "array",
            "description": "英語長文に出やすい単語（5個）",
            "items": {
                "type": "object",
                "properties": {"en": {"type": "string"}, "ja": {"type": "string"}},
                "required": ["en", "ja"],
                "additionalProperties": False,
            },
        },
        "word_forms": {
            "type": "array",
            "description": "語形変化（主に名詞化）3個。例: disclose（動）→ disclosure（名）",
            "items": {
                "type": "object",
                "properties": {
                    "base": {"type": "string"}, "base_pos": {"type": "string", "enum": ["動", "形", "名", "副"]},
                    "derived": {"type": "string"}, "derived_pos": {"type": "string", "enum": ["動", "形", "名", "副"]},
                },
                "required": ["base", "base_pos", "derived", "derived_pos"],
                "additionalProperties": False,
            },
        },
        "example_en": {"type": "string", "description": "テーマに沿った英語の例文（1文）"},
        "example_ja": {"type": "string", "description": "例文の和訳"},
    },
    "required": ["index_line", "headline", "subhead", "lead", "sources", "what_happened", "keio_angle",
                 "vocab", "word_forms", "example_en", "example_ja"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {"type": "string", "description": "本日のテーマ（例: 環境・エネルギー転換）15字以内"},
        "essays": {"type": "array", "items": ESSAY_SCHEMA},
        "english": {"type": "array", "items": ENGLISH_SCHEMA},
        "history": {
            "type": "object",
            "properties": {
                "index_line": {"type": "string", "description": "本日の紙面に載せる1行（40字以内）"},
                "paragraphs": {"type": "array", "items": {"type": "string"},
                               "description": "2段落、計300字程度。最後は今日のニュースにつなげて締める"},
            },
            "required": ["index_line", "paragraphs"],
            "additionalProperties": False,
        },
    },
    "required": ["theme", "essays", "english", "history"],
    "additionalProperties": False,
}


# --- テンプレート版（APIキーなし） -------------------------------------------

def template_essay(article):
    theme = THEME_BY_ID[article["theme"]]
    pro, con = theme["issues"][0].split(" vs ")
    return {
        "index_line": article["title"],
        "headline": article["title"],
        "subhead": f"{theme['name']}の具体例として読む",
        "lead": article.get("summary") or "",
        "sources": article["source"],
        "what_happened": "", "context_title": "なぜ重要か", "context": "", "points": [],
        "issue": theme["issues"][0].replace(" vs ", "か、") + "か",
        "pros": [pro], "cons": [con],
        "connection": "",
        "keywords": [{"term": c, "definition": ""} for c in theme["concepts"][:4]],
        "question": theme["question"],
        "answer_claim": "", "answer_reason": "", "answer_plan": "",
    }


def template_english(article):
    theme = ENGLISH_THEME_BY_ID[article["theme"]]
    return {
        "index_line": article["title"],
        "headline": article["title"],
        "subhead": theme["name"],
        "lead": article.get("summary") or "",
        "sources": article["source"],
        "what_happened": "",
        "keio_angle": theme["background"],
        "vocab": [{"en": en, "ja": ja} for en, ja in theme["vocab"]],
        "word_forms": [], "example_en": "", "example_ja": "",
    }


def template_paper(essays, english):
    return {
        "theme": THEME_BY_ID[essays[0]["theme"]]["name"] if essays else "",
        "essays": [template_essay(a) for a in essays],
        "english": [template_english(a) for a in english],
        "history": {"index_line": "", "paragraphs": []},
    }


# --- Claude 版 -----------------------------------------------------------------

def _faculty_names(article):
    return "・".join(FACULTY_BY_ID[f]["name"] for f in article["faculties"])


def _article_list(essays, english):
    parts = ["## 小論文面"]
    for i, a in enumerate(essays):
        parts.append(f"[小論文{i + 1}] 対象: {_faculty_names(a)}（テーマ: {THEME_BY_ID[a['theme']]['name']}）\n"
                     f"見出し: {a['title']}\n概要: {a.get('summary') or '（なし）'}\n配信: {a['source']}\nURL: {a['link']}")
    parts.append("## 英語長文面（経済・商学部）")
    for i, a in enumerate(english):
        parts.append(f"[英語{i + 1}] 分野: {ENGLISH_THEME_BY_ID[a['theme']]['name']}\n"
                     f"Title: {a['title']}\nSummary: {a.get('summary') or '(none)'}\nSource: {a['source']}\nURL: {a['link']}")
    return "\n\n".join(parts)


def _create(client, **kwargs):
    response = client.beta.messages.create(
        model=MODEL, max_tokens=16000,
        # 安全分類器による辞退時はサーバー側で推奨モデルに切り替えて再実行する
        betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude が生成を辞退しました")
    return response


def research(client, essays, english):
    """Web検索・取得で事実関係を調べ、取材メモ（テキスト）を返す。"""
    user = {"role": "user", "content": "次のニュースを取材してください。\n\n" + _article_list(essays, english)}
    content = []
    for _ in range(MAX_CONTINUATIONS):
        messages = [user] + ([{"role": "assistant", "content": content}] if content else [])
        response = _create(client, system=RESEARCH_SYSTEM, tools=RESEARCH_TOOLS, messages=messages,
                           output_config={"effort": "medium"})
        content = content + list(response.content)
        # サーバー側ツールの反復上限に達すると pause_turn で止まるので、続きから再開する
        if response.stop_reason != "pause_turn":
            break
    notes = "\n".join(b.text for b in content if b.type == "text").strip()
    if not notes:
        raise RuntimeError("取材メモが空でした")
    return notes


def write(client, essays, english, notes):
    prompt = (f"{_article_list(essays, english)}\n\n## 取材メモ\n{notes}\n\n"
              "上の記事と取材メモから、今日の紙面を書いてください。essays と english は入力と同じ順番・同じ件数で。")
    response = _create(client, system=WRITER_SYSTEM, messages=[{"role": "user", "content": prompt}],
                       output_config={"effort": "high",
                                      "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}})
    if response.stop_reason == "max_tokens":
        raise RuntimeError("出力が max_tokens で途切れました")
    data = json.loads(next(b.text for b in response.content if b.type == "text"))
    if len(data["essays"]) != len(essays) or len(data["english"]) != len(english):
        raise RuntimeError("記事数が一致しません")
    return data


def claude_paper(essays, english):
    import anthropic

    client = anthropic.Anthropic()
    return write(client, essays, english, research(client, essays, english))


def enrich(essays, english):
    """(紙面付きの小論文記事, 紙面付きの英語記事, 本日のテーマ, 世界史の窓, 生成元) を返す。"""
    data, by = None, "template"
    if (essays or english) and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            data, by = claude_paper(essays, english), "claude"
        except Exception as e:
            print(f"[warn] Claude での紙面作成に失敗したため簡易版にします: {e}", file=sys.stderr)
    if data is None:
        data = template_paper(essays, english)
    essays = [{**a, "paper": p, "generated_by": by} for a, p in zip(essays, data["essays"])]
    english = [{**a, "paper": p, "generated_by": by} for a, p in zip(english, data["english"])]
    return essays, english, data["theme"], data["history"], by
