"""記事を「入試の素材としての価値」で採点し、学部・分野が偏らないように選ぶ。"""

import re

from .themes import (ENGLISH_NOISE_WORDS, ENGLISH_POLICY_WORDS, ENGLISH_THEMES, FACULTIES,
                     NOISE_WORDS, POLICY_WORDS, THEME_BY_ID, THEMES)

ESSAY = (THEMES, POLICY_WORDS, NOISE_WORDS)
ENGLISH = (ENGLISH_THEMES, ENGLISH_POLICY_WORDS, ENGLISH_NOISE_WORDS)


def _count(text, word):
    # 英字の語（AI 等）は単語境界で数え、"MAIL" などへの誤反応を防ぐ
    if word.isascii():
        return len(re.findall(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", text))
    return text.count(word)


def theme_scores(article, kind=ESSAY):
    """テーマごとの得点（キーワード一致＋政策語ボーナス−ノイズ減点）。タイトルの一致を重く見る。"""
    themes, policy, noise = kind
    english = kind is ENGLISH
    title, summary = article["title"], article.get("summary", "")
    if english:
        title, summary = title.lower(), summary.lower()
    text = title + " " + summary
    bonus = 2 * sum(1 for w in policy if _count(text, w)) - 6 * sum(1 for w in noise if _count(text, w))
    scores = {}
    for theme in themes:
        s = sum(3 * _count(title, kw) + _count(summary, kw) for kw in theme["keywords"])
        if s:
            scores[theme["id"]] = s + bonus
    return scores


def score(article, kind=ESSAY):
    scores = theme_scores(article, kind)
    if not scores:
        return 0, None
    best = max(scores, key=scores.get)
    return scores[best], best


def _norm(title):
    return re.sub(r"[\s　「」『』【】（）()、。・:：!！?？\-－'\"‘’“”]", "", title.lower())[:40]


def similar(a, b):
    """タイトルの文字bigramの重なりで同一ニュースの別配信を見分ける。"""
    grams = lambda s: {s[i:i + 2] for i in range(len(s) - 1)}
    ga, gb = grams(_norm(a)), grams(_norm(b))
    if not ga or not gb:
        return False
    return len(ga & gb) / min(len(ga), len(gb)) > 0.6


def _candidates(articles, kind, exclude_titles, min_score):
    """重複と直近に出した記事を除き、(記事, テーマ別得点) を最高点の順に返す。"""
    scored = []
    for a in articles:
        scores = {t: s for t, s in theme_scores(a, kind).items() if s >= min_score}
        if scores:
            scored.append((a, scores))
    scored.sort(key=lambda x: max(x[1].values()), reverse=True)
    unique = []
    for a, scores in scored:
        if any(similar(a["title"], t) for t in exclude_titles):
            continue
        if any(similar(a["title"], u["title"]) for u, _ in unique):
            continue
        unique.append((a, scores))
    return unique


def pick_essays(articles, faculties=None, exclude_titles=(), min_score=4):
    """学部ごとに1本ずつ選ぶ。候補の少ない学部（文→法→環境情報→総合政策）から順に割り当てる。"""
    faculties = faculties or [f["id"] for f in FACULTIES]
    cands = _candidates(articles, ESSAY, exclude_titles, min_score)
    chosen, used = {}, set()
    for fac in faculties:
        best = None
        for i, (a, scores) in enumerate(cands):
            if i in used:
                continue
            for theme, s in scores.items():
                faculties_of_theme = THEME_BY_ID[theme]["faculties"]
                if fac not in faculties_of_theme:
                    continue
                if faculties_of_theme[0] == fac:  # 本命の学部なら優先する
                    s *= 1.5
                if best is None or s > best[2]:
                    best = (i, theme, s)
        if best:
            i, theme, s = best
            used.add(i)
            chosen[fac] = {**cands[i][0], "theme": theme, "score": s, "faculty": fac}
    return chosen


def pick_english(articles, n=2, exclude_titles=(), min_score=4):
    """英語記事を分野が重ならないように n 本選ぶ。"""
    chosen, used = [], set()
    for a, scores in _candidates(articles, ENGLISH, exclude_titles, min_score):
        theme = max(scores, key=scores.get)
        if theme in used:
            continue
        chosen.append({**a, "theme": theme, "score": scores[theme]})
        used.add(theme)
        if len(chosen) == n:
            break
    return chosen
