"""選んだ記事に「入試対策としての読み方」を付ける。

ANTHROPIC_API_KEY があれば Claude が記事ごとの解説を書く。
無い場合や失敗した場合は、テーマ定義に基づくテンプレートで補う。
解説は記事 dict の "notes" に入れて返す（復習モードでそのまま再利用するため）。
"""

import json
import os
import sys

from .themes import ENGLISH_THEME_BY_ID, FACULTY_BY_ID, THEME_BY_ID

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """あなたは慶應義塾大学の入試対策を指導するプロの受験コーチです。
受験生（高校3年生）が毎朝【合計10分】で読み切れる分量で、ニュースを入試の素材として解説してください。

対象:
- 小論文：文学部・法学部・環境情報学部・総合政策学部。記事ごとに指定された学部の傾向に合わせて論点と設問を立てる。
- 英語長文：経済学部・商学部。英文記事を、長文読解の「背景知識」と「語彙」の予習として解説する。

方針:
- 10分で読める分量を厳守する。各フィールドの字数上限を守り、1文を短く。
- 記事の見出し・概要に書かれていない具体的な数値や固有名詞は創作しない。背景説明は一般的に知られている範囲にとどめる。
- 入試問題は本番の数か月前に作られるため、個別のニュースそのものより「その背後にある長く議論されてきたテーマ」を押さえさせる。
- 賛否は必ず両側を示し、どちらの立場でも書けるようにする。
- 高校生にわかる言葉で。絵文字は daily_message にだけ少し使ってよい。"""

ESSAY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "記事の要点（80字以内）"},
        "angle": {"type": "string", "description": "指定学部の小論文でどう使えるか・どんな長期的テーマにつながるか（80字以内）"},
        "pros": {"type": "array", "items": {"type": "string"}, "description": "推進・賛成側の論拠（1〜2個、各40字以内）"},
        "cons": {"type": "array", "items": {"type": "string"}, "description": "慎重・反対側の論拠（1〜2個、各40字以内）"},
        "concepts": {"type": "array", "items": {"type": "string"}, "description": "答案で使える概念（3個）"},
        "question": {"type": "string", "description": "指定学部の傾向に合わせた小論文の設問（60字以内）"},
        "outline": {"type": "array", "items": {"type": "string"},
                    "description": "答案の構成メモ4行 [問題提起, 原因分析, 解決策（または自説の根拠）, 結論]（各40字以内）"},
    },
    "required": ["summary", "angle", "pros", "cons", "concepts", "question", "outline"],
    "additionalProperties": False,
}

ENGLISH_NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary_ja": {"type": "string", "description": "英文記事の要点を日本語で（100字以内）"},
        "background": {"type": "string", "description": "経済・商学部の英語長文を読むときに役立つ背景知識（120字以内）"},
        "passage_angle": {"type": "string", "description": "入試の英文ではこのテーマがどんな論じ方で出やすいか（60字以内）"},
        "vocab": {
            "type": "array",
            "description": "記事のテーマで長文に出やすい英単語・熟語（5個）",
            "items": {
                "type": "object",
                "properties": {"en": {"type": "string"}, "ja": {"type": "string"}},
                "required": ["en", "ja"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary_ja", "background", "passage_angle", "vocab"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "essays": {"type": "array", "items": ESSAY_SCHEMA},
        "english": {"type": "array", "items": ENGLISH_NOTE_SCHEMA},
        "daily_message": {"type": "string", "description": "受験生への今朝の一言（1〜2文）"},
    },
    "required": ["essays", "english", "daily_message"],
    "additionalProperties": False,
}


def template_essay(article):
    theme = THEME_BY_ID[article["theme"]]
    faculty = FACULTY_BY_ID[article["faculty"]]
    pro, con = theme["issues"][0].split(" vs ")
    return {
        "summary": article.get("summary") or "（概要なし。リンク先で本文を確認しよう）",
        "angle": f"{faculty['name']}：{faculty['style']}「{theme['name']}」の具体例として使える。",
        "pros": [pro],
        "cons": [con],
        "concepts": theme["concepts"][:3],
        "question": theme["question"],
        "outline": ["問題提起：このニュースが示す課題・問いは何か",
                    "原因分析：なぜそれが起きているのか（構造・制度・価値観）",
                    "解決策・自説の根拠：誰が何をすべきか／なぜそう考えるか",
                    "結論：自分の立場を一文で"],
    }


def template_english(article):
    theme = ENGLISH_THEME_BY_ID[article["theme"]]
    return {
        "summary_ja": article.get("summary") or "（概要なし。リンク先で英文を読んでみよう）",
        "background": theme["background"],
        "passage_angle": f"「{theme['name']}」は評論・論説文として出やすい。筆者の主張と具体例を区別して読もう。",
        "vocab": [{"en": en, "ja": ja} for en, ja in theme["vocab"]],
    }


TEMPLATE_MESSAGE = "今日のメイン設問を「問題→原因→解決策」の3行でまとめてみよう ✍️"


def _prompt(essays, english):
    parts = ["今朝のニュースです。essays と english は入力と同じ順番・同じ件数で返してください。", "", "## 小論文用"]
    for i, a in enumerate(essays):
        fac = FACULTY_BY_ID[a["faculty"]]
        parts.append(f"[{i}] 対象学部: {fac['name']}（傾向: {fac['style']}）\nテーマ: {THEME_BY_ID[a['theme']]['name']}\n"
                     f"見出し: {a['title']}\n概要: {a.get('summary') or '（なし）'}\n配信: {a['source']}")
    parts += ["", "## 英語長文（経済・商学部）用"]
    for i, a in enumerate(english):
        parts.append(f"[{i}] 分野: {ENGLISH_THEME_BY_ID[a['theme']]['name']}\n"
                     f"Title: {a['title']}\nSummary: {a.get('summary') or '(none)'}\nSource: {a['source']}")
    return "\n".join(parts)


def claude_enrich(essays, english):
    import anthropic

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _prompt(essays, english)}],
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
        # 安全分類器による辞退時はサーバー側で推奨モデルに切り替えて再実行する
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude が生成を辞退しました")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("出力が max_tokens で途切れました")
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    if len(data["essays"]) != len(essays) or len(data["english"]) != len(english):
        raise RuntimeError("記事数が一致しません")
    return data


def enrich(essays, english):
    """(解説付きの小論文記事, 解説付きの英語記事, 今朝の一言, 生成元) を返す。"""
    data, by = None, "template"
    if (essays or english) and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            data, by = claude_enrich(essays, english), "claude"
        except Exception as e:
            print(f"[warn] Claude での解説生成に失敗したためテンプレートを使います: {e}", file=sys.stderr)
    if data is None:
        data = {"essays": [template_essay(a) for a in essays],
                "english": [template_english(a) for a in english],
                "daily_message": TEMPLATE_MESSAGE}
    essays = [{**a, "notes": n, "generated_by": by} for a, n in zip(essays, data["essays"])]
    english = [{**a, "notes": n, "generated_by": by} for a, n in zip(english, data["english"])]
    return essays, english, data["daily_message"], by
