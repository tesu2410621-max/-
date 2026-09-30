"""記事を「入試の素材としての価値」で採点し、学部・分野が偏らないように選ぶ。"""

import re

from .themes import (DOMESTIC_POLITICS_WORDS, ENGLISH_NOISE_WORDS, ENGLISH_POLICY_WORDS, ENGLISH_THEMES,
                     FACULTIES, NOISE_WORDS, POLICY_WORDS, THEME_BY_ID, THEMES)

# (テーマ, 政策語, 減点語, キーワードの項目名, 英文か)
ESSAY = (THEMES, POLICY_WORDS, NOISE_WORDS + DOMESTIC_POLITICS_WORDS, "keywords", False)
ESSAY_EN = (THEMES, ENGLISH_POLICY_WORDS, ENGLISH_NOISE_WORDS, "keywords_en", True)  # 海外の英文記事を小論文面に
ENGLISH = (ENGLISH_THEMES, ENGLISH_POLICY_WORDS, ENGLISH_NOISE_WORDS, "keywords", True)

# 国内の話題に偏らないよう、海外のニュースを優先する
INTERNATIONAL_BONUS = 4


def _count(text, word):
    # 英字の語（AI 等）は単語境界で数え、"MAIL" などへの誤反応を防ぐ
    if word.isascii():
        return len(re.findall(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", text))
    return text.count(word)


def theme_scores(article, kind=ESSAY):
    """テーマごとの得点（キーワード一致＋政策語ボーナス−ノイズ減点）。タイトルの一致を重く見る。"""
    themes, policy, noise, key, english = kind
    title, summary = article["title"], article.get("summary", "")
    if english:
        title, summary = title.lower(), summary.lower()
    text = title + " " + summary
    bonus = 2 * sum(1 for w in policy if _count(text, w)) - 6 * sum(1 for w in noise if _count(text, w))
    if not english and len(article["title"]) > 70:  # 長すぎる見出しは広報文であることが多い
        bonus -= 6
    if any(ord(c) > 0xFFFF for c in article["title"]):  # 絵文字入りの見出しは告知・宣伝であることが多い
        bonus -= 8
    scores = {}
    for theme in themes:
        s = sum(3 * _count(title, kw) + _count(summary, kw) for kw in theme.get(key, []))
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


def _trigrams(title):
    title = re.sub(r"【[^】]*】", "", title)  # 【速報】などのラベルは話題ではない
    words = re.findall(r"[一-龥々ァ-ヴー]{3,}", title)
    return {w[i:i + 3] for w in words for i in range(len(w) - 2)}


# 役職・機関名など、話題が違っても見出しによく出る3文字列
COMMON_TRIGRAMS = {"官房長", "房長官", "臨時国", "時国会", "通常国", "常国会", "自民党", "立憲民", "衆議院", "参議院",
                   "大統領", "首相官", "委員会", "研究所", "文部科", "部科学", "科学省", "厚生労", "生労働", "労働省",
                   "経済産", "済産業", "産業省", "国土交", "土交通", "交通省", "総務省", "外務省", "財務省", "警察庁"}


def same_topic(a, b):
    """「消費税」のような話題を表す漢字・カタカナの3文字列を共有していれば同じ話題とみなす。"""
    return bool((_trigrams(a) & _trigrams(b)) - COMMON_TRIGRAMS)


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


def _international(article, scores):
    return {t: v + INTERNATIONAL_BONUS for t, v in scores.items()}


def essay_candidates(articles, en_articles=(), exclude_titles=(), min_score=4):
    """日本語記事と海外の英文記事を合わせた小論文の候補。海外（英文・国際面）の記事は加点する。"""
    cands = [(a, _international(a, sc) if "国際" in a["source"] else sc)
             for a, sc in _candidates(articles, ESSAY, exclude_titles, min_score)]
    cands += [({**a, "lang": "en"}, _international(a, sc))
              for a, sc in _candidates(en_articles, ESSAY_EN, exclude_titles, min_score)]
    return sorted(cands, key=lambda x: max(x[1].values()), reverse=True)


def pick_essays(articles, faculties=None, exclude_titles=(), min_score=4, en_articles=()):
    """学部ごとに1本ずつ選ぶ。与えられた学部の順に、話題が重ならないよう割り当てる。"""
    faculties = faculties or [f["id"] for f in FACULTIES]
    cands = essay_candidates(articles, en_articles, exclude_titles, min_score)
    chosen, used = {}, set()
    for fac in faculties:
        best = None
        for i, (a, scores) in enumerate(cands):
            if i in used or any(same_topic(a["title"], c["title"]) or similar(a["title"], c["title"])
                                for c in chosen.values()):
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
