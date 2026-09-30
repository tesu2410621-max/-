"""選んだ記事に「小論文としての読み方」を付ける。

ANTHROPIC_API_KEY があれば Claude が記事ごとに要約・論点・設問・構成メモを作る。
無い場合や失敗した場合は、テーマ定義に基づくテンプレートで補う。
"""

import json
import os
import sys

from .themes import THEME_BY_ID

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """あなたは慶應義塾大学の小論文（特に総合政策学部）を指導するプロの受験コーチです。
受験生（高校3年生、9月の実戦期）が毎朝5分で読み、小論文の「引き出し」を増やせるように、
与えられたニュース記事を小論文の素材として解説してください。

方針:
- 記事の見出し・概要に書かれていない具体的な数値や固有名詞は創作しないこと。背景説明は一般的に知られている範囲にとどめる。
- 総合政策学部の小論文は「問題発見→原因分析→解決策の提案」と、資料・データの読み取りを重視する。その視点で論点を立てる。
- 賛否は必ず両側を示し、どちらの立場でも書けるようにする。
- 高校生にわかる言葉で、簡潔に。絵文字は daily_message にだけ少し使ってよい。"""

ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "記事の要点を2〜3文で"},
        "why_it_matters": {"type": "string", "description": "なぜ小論文の素材になるのか（どんな社会課題につながるか）1〜2文"},
        "pros": {"type": "array", "items": {"type": "string"}, "description": "推進・賛成側の論拠（2つ）"},
        "cons": {"type": "array", "items": {"type": "string"}, "description": "慎重・反対側の論拠（2つ）"},
        "concepts": {"type": "array", "items": {"type": "string"}, "description": "答案で使える概念・キーワード（3〜4個）"},
        "question": {"type": "string", "description": "このニュースから作る小論文の設問（総合政策学部風）"},
        "outline": {"type": "array", "items": {"type": "string"},
                    "description": "設問への答案の構成メモ。[問題提起, 原因分析, 解決策, 結論] の4要素"},
    },
    "required": ["summary", "why_it_matters", "pros", "cons", "concepts", "question", "outline"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "articles": {"type": "array", "items": ARTICLE_SCHEMA},
        "main_index": {"type": "integer", "description": "今日じっくり書く1本（0始まりの番号）"},
        "daily_message": {"type": "string", "description": "受験生への今朝の一言（1〜2文）"},
    },
    "required": ["articles", "main_index", "daily_message"],
    "additionalProperties": False,
}


def template_notes(article):
    theme = THEME_BY_ID[article["theme"]]
    return {
        "summary": article.get("summary") or "（概要なし。リンク先で本文を確認しよう）",
        "why_it_matters": f"「{theme['name']}」の具体例として使える。抽象論だけの答案に説得力を与える材料になる。",
        "pros": [theme["issues"][0].split(" vs ")[0]],
        "cons": [theme["issues"][0].split(" vs ")[1]],
        "concepts": theme["concepts"][:4],
        "question": theme["question"],
        "outline": ["問題提起：このニュースが示す社会課題は何か",
                    "原因分析：なぜその課題が生じているのか（構造・制度・インセンティブ）",
                    "解決策：誰が何をすべきか。副作用とその対処も",
                    "結論：自分の立場を一文で"],
    }


def template_enrich(articles):
    return {
        "articles": [template_notes(a) for a in articles],
        "main_index": 0,
        "daily_message": "今日の1本を「問題発見→原因→解決策」の3行でまとめてみよう ✍️",
        "generated_by": "template",
    }


def _prompt(articles):
    lines = []
    for i, a in enumerate(articles):
        theme = THEME_BY_ID[a["theme"]]["name"]
        lines.append(f"[{i}] テーマ: {theme}\n見出し: {a['title']}\n概要: {a.get('summary') or '（なし）'}\n配信: {a['source']}")
    return ("今朝のニュースです。articles は入力と同じ順番・同じ件数で返してください。\n\n"
            + "\n\n".join(lines))


def claude_enrich(articles):
    import anthropic

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _prompt(articles)}],
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
    if len(data["articles"]) != len(articles):
        raise RuntimeError("記事数が一致しません")
    if not 0 <= data["main_index"] < len(articles):
        data["main_index"] = 0
    data["generated_by"] = "claude"
    return data


def enrich(articles):
    if articles and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return claude_enrich(articles)
        except Exception as e:
            print(f"[warn] Claude での解説生成に失敗したためテンプレートを使います: {e}", file=sys.stderr)
    return template_enrich(articles)
