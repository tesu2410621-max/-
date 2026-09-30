"""記事を「小論文の素材としての価値」で採点し、テーマが偏らないように選ぶ。"""

import re

from .themes import NOISE_WORDS, POLICY_WORDS, THEMES


def _count(text, word):
    # 英字の短い語（AI 等）は単語境界で数え、"MAIL" などへの誤反応を防ぐ
    if word.isascii():
        return len(re.findall(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", text))
    return text.count(word)


def classify(article):
    """記事のテーマ別スコアを返す。タイトルでの一致を本文より重く見る。"""
    title, summary = article["title"], article.get("summary", "")
    scores = {}
    for theme in THEMES:
        s = sum(3 * _count(title, kw) + _count(summary, kw) for kw in theme["keywords"])
        if s:
            scores[theme["id"]] = s
    return scores


def score(article):
    text = article["title"] + " " + article.get("summary", "")
    theme_scores = classify(article)
    if not theme_scores:
        return 0, None
    best = max(theme_scores, key=theme_scores.get)
    total = theme_scores[best] + 0.5 * (sum(theme_scores.values()) - theme_scores[best])
    total += 2 * sum(1 for w in POLICY_WORDS if w in text)
    total -= 6 * sum(1 for w in NOISE_WORDS if w in text)
    return total, best


def _norm(title):
    return re.sub(r"[\s　「」『』【】（）()、。・:：!！?？\-－]", "", title)[:40]


def _similar(a, b):
    """タイトルの文字bigramの重なりで同一ニュースの別配信を見分ける。"""
    grams = lambda s: {s[i:i + 2] for i in range(len(s) - 1)}
    ga, gb = grams(_norm(a)), grams(_norm(b))
    if not ga or not gb:
        return False
    return len(ga & gb) / min(len(ga), len(gb)) > 0.6


def pick(articles, n=5, exclude_titles=(), min_score=4):
    """上位からテーマが重ならないよう n 本選び、足りなければ重複テーマで補う。"""
    ranked = []
    for a in articles:
        s, theme = score(a)
        if theme and s >= min_score:
            ranked.append({**a, "score": s, "theme": theme})
    ranked.sort(key=lambda a: a["score"], reverse=True)

    unique = []
    for a in ranked:
        if any(_similar(a["title"], t) for t in exclude_titles):
            continue
        if any(_similar(a["title"], u["title"]) for u in unique):
            continue
        unique.append(a)

    chosen, used = [], set()
    for a in unique:
        if a["theme"] not in used:
            chosen.append(a)
            used.add(a["theme"])
        if len(chosen) == n:
            return chosen
    for a in unique:
        if a not in chosen:
            chosen.append(a)
        if len(chosen) == n:
            break
    return chosen
