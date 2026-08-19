"""纯函数：submissions → 按天聚合 / 总览统计（无 IO，便于单测）。

统计口径（见 activity/conventions.md，与前端 mock 对齐）：
- 解题数 = 当天 AC 的不同题目数（重复提交不重复计；汇总不做跨平台去重，
  去重键含 platform，故不同平台同题号自然分开）；
- 连续天数按"当天有 AC"计；今天尚无 AC 时不算断签，统计到昨天为止；
- 热力图固定近 WINDOW_DAYS 天（近一年，含今天）。
"""

from collections.abc import Iterable
from datetime import date, datetime, timedelta, tzinfo

from adapters.base import Verdict
from modules.activity.models import Submission

WINDOW_DAYS = 370  # 对齐前端热力图窗口（53 周）


def _local_date(ts: int, tz: tzinfo) -> date:
    return datetime.fromtimestamp(ts, tz=tz).date()


def daily_series(
    submissions: Iterable[Submission],
    *,
    tz: tzinfo,
    days: int = WINDOW_DAYS,
) -> list[dict[str, int]]:
    """近 days 天日序列 [{date, submissions, solved}]，升序，末尾为今天。"""
    today = datetime.now(tz=tz).date()
    start = today - timedelta(days=days - 1)
    counts: dict[date, int] = {}
    ac_keys: dict[date, set[tuple[str, str]]] = {}
    for s in submissions:
        d = _local_date(s.submitted_at, tz)
        if d < start or d > today:
            continue
        counts[d] = counts.get(d, 0) + 1
        if s.verdict == Verdict.AC:
            ac_keys.setdefault(d, set()).add((s.platform, s.problem_key))
    out: list[dict[str, int]] = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append(
            {
                "date": d.isoformat(),
                "submissions": counts.get(d, 0),
                "solved": len(ac_keys.get(d, set())),
            }
        )
    return out


def overview_stats(
    submissions: Iterable[Submission],
    *,
    tz: tzinfo,
) -> dict[str, int]:
    """all-time 总量 + 今日/近 7 天 + 连续活跃天数。

    返回键对齐前端 OverviewTotals（camelCase）：
    totalSolved / totalSubmissions / todaySolved / weekSolved / streakDays。
    """
    total_submissions = 0
    ac_keys_all: set[tuple[str, str]] = set()
    ac_days: set[date] = set()
    today = datetime.now(tz=tz).date()
    week_start = today - timedelta(days=6)
    ac_by_day: dict[date, set[tuple[str, str]]] = {}
    for s in submissions:
        total_submissions += 1
        if s.verdict != Verdict.AC:
            continue
        d = _local_date(s.submitted_at, tz)
        key = (s.platform, s.problem_key)
        ac_keys_all.add(key)
        ac_days.add(d)
        if week_start <= d <= today:
            ac_by_day.setdefault(d, set()).add(key)
    return {
        "totalSolved": len(ac_keys_all),
        "totalSubmissions": total_submissions,
        "todaySolved": len(ac_by_day.get(today, set())),
        "weekSolved": sum(len(v) for v in ac_by_day.values()),
        "streakDays": _streak_days(ac_days, today),
    }


def _streak_days(ac_days: set[date], today: date) -> int:
    """连续活跃天数：按"当天有 AC"计，今天无 AC 不算断签（从昨天起数）。"""
    if not ac_days:
        return 0
    cur = today
    if cur not in ac_days:
        cur -= timedelta(days=1)
    n = 0
    while cur in ac_days:
        n += 1
        cur -= timedelta(days=1)
    return n
