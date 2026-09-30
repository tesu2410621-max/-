"""入試の「出題圏内」を判定する。

入試問題は本番の数か月前に作られるため、出題に反映されうるニュースは
おおむね11月までと考える。12月〜3月は直前のニュースを追うのをやめ、
出題圏内（前年12月〜11月）に集めた記事を復習するモードに切り替える。
"""

import datetime


def season(day):
    """day（date）に対する (mode, 出題圏の開始日, 出題圏の締切日, 入試年) を返す。"""
    if day.month >= 4:
        cutoff = datetime.date(day.year, 11, 30)
    else:
        cutoff = datetime.date(day.year - 1, 11, 30)
    start = datetime.date(cutoff.year - 1, 12, 1)
    mode = "live" if day <= cutoff else "review"
    return mode, start, cutoff, cutoff.year + 1


def banner(day):
    mode, start, cutoff, exam_year = season(day)
    left = (cutoff - day).days
    if mode == "review":
        return ("review", f"🧊 {exam_year}年入試の出題圏は{cutoff.month}月{cutoff.day}日で締め切り。"
                "直前のニュースは作問に間に合わないので、ここからは出題圏内に集めたニュースの復習です。")
    if day.month >= 10:
        return ("live", f"⏳ 出題圏の締め切り（11月末）まであと{left}日。"
                "10〜11月は入試に反映されうる最後のニュースです。ここで押さえた話題が本番の引き出しになります。")
    return ("live", f"🟢 今日のニュースは{exam_year}年入試の出題圏内です（締め切りの目安：{cutoff.year}年11月末）。")


def in_window(date_str, day):
    """アーカイブ記事の日付が、day の入試シーズンの出題圏内にあるか。"""
    _, start, cutoff, _ = season(day)
    d = datetime.date.fromisoformat(date_str)
    return start <= d <= cutoff
