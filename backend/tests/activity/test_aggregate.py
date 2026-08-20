"""aggregate 纯函数测试：按天切分（本地时区）、去重口径、窗口、streak。"""

from datetime import datetime, timedelta, timezone

from adapters.base import Verdict
from modules.activity.aggregate import WINDOW_DAYS, daily_series, overview_stats
from modules.activity.models import Submission

TZ = timezone(timedelta(hours=8))  # UTC+8 固定偏移，测试不依赖系统时区


def ts_at(days_ago: int, hour: int = 10, minute: int = 0) -> int:
    """本地时区某天某时刻的 UTC 时间戳。"""
    today = datetime.now(TZ).date()
    d = today - timedelta(days=days_ago)
    return int(datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ).timestamp())


def sub(
    sid: str,
    key: str = "2245A",
    verdict: str = "AC",
    days_ago: int = 0,
    platform: str = "codeforces",
) -> Submission:
    return Submission(
        platform=platform,
        handle="demo",
        submission_id=sid,
        problem_key=key,
        problem_name="X",
        problem_url="https://codeforces.com/contest/2245/problem/A",
        verdict=Verdict(verdict),
        submitted_at=ts_at(days_ago),
        language="GNU C++17",
    )


def test_daily_series_window_and_order():
    items = [
        sub("1", days_ago=0),
        sub("2", days_ago=1),
        sub("3", days_ago=400),  # 窗口外
    ]
    series = daily_series(items, tz=TZ)
    assert len(series) == WINDOW_DAYS
    assert series[-1]["date"] == datetime.now(TZ).date().isoformat()
    assert series[-1]["submissions"] == 1
    assert series[-2]["submissions"] == 1
    dates = [d["date"] for d in series]
    assert dates == sorted(dates)
    assert all(d["submissions"] == 0 for d in series[:-2])


def test_daily_solved_deduplicates_by_problem():
    """当天同一题多次提交只算一个解题数；提交数累计。"""
    items = [
        sub("1", key="2245A", verdict="AC"),
        sub("2", key="2245A", verdict="AC"),  # 重复提交
        sub("3", key="2245B", verdict="AC"),
        sub("4", key="2245B", verdict="WA"),
        sub("5", key="2245B", verdict="AC"),
    ]
    series = daily_series(items, tz=TZ)
    today = series[-1]
    assert today["submissions"] == 5
    assert today["solved"] == 2  # 2245A / 2245B 各一题


def test_overview_totals():
    items = [
        sub("1", key="2245A", verdict="AC", days_ago=0),
        sub("2", key="2245B", verdict="AC", days_ago=1),
        sub("3", key="2245B", verdict="AC", days_ago=1),
        sub("4", key="2245C", verdict="WA", days_ago=5),
        sub("5", key="2245D", verdict="AC", days_ago=100),
    ]
    stats = overview_stats(items, tz=TZ)
    assert stats["totalSubmissions"] == 5
    assert stats["totalSolved"] == 3  # A/B/D（C 是 WA 不计）
    assert stats["todaySolved"] == 1
    assert stats["weekSolved"] == 2  # 今天 A + 昨天 B（去重）
    # streak：今天 + 昨天有 AC → 2（100 天前的 D 断开）
    assert stats["streakDays"] == 2


def test_streak_today_without_ac_counts_from_yesterday():
    """今天无 AC 不算断签，从昨天向前数。"""
    items = [
        sub("1", key="2245A", verdict="AC", days_ago=1),
        sub("2", key="2245B", verdict="AC", days_ago=2),
        sub("3", key="2245C", verdict="WA", days_ago=0),  # 今天只有 WA
    ]
    stats = overview_stats(items, tz=TZ)
    assert stats["streakDays"] == 2
    assert stats["todaySolved"] == 0


def test_streak_empty():
    stats = overview_stats([], tz=TZ)
    assert stats["streakDays"] == 0
    assert stats["totalSolved"] == 0
    series = daily_series([], tz=TZ)
    assert len(series) == WINDOW_DAYS
    assert series[-1]["solved"] == 0


def test_overview_cross_platform_keys_separate():
    """汇总不做跨平台去重：同题号不同平台各算一题。"""
    items = [
        sub("1", key="P1001", verdict="AC", platform="codeforces"),
        sub("2", key="P1001", verdict="AC", platform="luogu"),
    ]
    stats = overview_stats(items, tz=TZ)
    assert stats["totalSolved"] == 2
