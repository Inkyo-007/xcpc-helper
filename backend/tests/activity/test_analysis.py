"""analysis 纯函数测试：难度分桶、verdict 全枚举、训练节奏、薄弱点口径。"""

from datetime import datetime, timedelta, timezone

from adapters.base import Verdict
from modules.activity.analysis import (
    DIFFICULTY_BANDS,
    _numeric_difficulty,
    build_analysis,
    difficulty_distribution,
    training_rhythm,
    verdict_distribution,
    weak_points,
)
from modules.activity.models import Submission
from modules.activity.skill_tree import build_skill_tree

TZ = timezone(timedelta(hours=8))  # UTC+8 固定偏移，测试不依赖系统时区


def sub(
    sid: str,
    key: str = "2245A",
    verdict: str = "AC",
    tags: tuple[str, ...] = ("math",),
    difficulty: int | None = 800,
    platform: str = "codeforces",
    ts: int = 0,
) -> Submission:
    return Submission(
        platform=platform,
        handle="demo",
        submission_id=sid,
        problem_key=key,
        problem_name="X",
        problem_url="https://codeforces.com/contest/2245/problem/A",
        difficulty=difficulty,
        tags=list(tags),
        verdict=Verdict(verdict),
        submitted_at=ts,
        language="GNU C++17",
    )


def bands_by_label(dist: list[dict]) -> dict[str, dict]:
    return {b["label"]: b for b in dist}


# ===== 难度分布 =====


def test_difficulty_dedup_and_max():
    """同题多次提交去重，难度取最大数值难度，passRate 按去重题计。"""
    items = [
        sub("1", key="A", verdict="WA", difficulty=800),
        sub("2", key="A", verdict="AC", difficulty=1400),
        sub("3", key="A", verdict="AC", difficulty=1200),
    ]
    bands = bands_by_label(difficulty_distribution(items))
    band = bands["1400–1599"]
    assert band["solvedCount"] == 1
    assert band["attemptCount"] == 1
    assert band["submissionCount"] == 3
    assert band["passRate"] == 1.0
    assert bands["≤1199"]["attemptCount"] == 0


def test_difficulty_band_boundaries():
    """分档边界：1199 归 ≤1199、1200 归 1200–1399、2599/2600 各自归位。"""
    items = [
        sub("1", key="A", difficulty=1199),
        sub("2", key="B", difficulty=1200),
        sub("3", key="C", difficulty=2599),
        sub("4", key="D", difficulty=2600),
    ]
    bands = bands_by_label(difficulty_distribution(items))
    assert bands["≤1199"]["attemptCount"] == 1
    assert bands["1200–1399"]["attemptCount"] == 1
    assert bands["2400–2599"]["attemptCount"] == 1
    assert bands["2600+"]["attemptCount"] == 1


def test_difficulty_unknown_band():
    """无任何数值难度归未知档；min/max 为 None；passRate 边界。"""
    items = [
        sub("1", key="A", difficulty=None),
        sub("2", key="B", difficulty=None, verdict="WA"),
    ]
    unknown = bands_by_label(difficulty_distribution(items))["未知"]
    assert unknown["attemptCount"] == 2
    assert unknown["solvedCount"] == 1  # A 为 AC，B 为 WA
    assert unknown["submissionCount"] == 2
    assert unknown["passRate"] == 0.5
    assert unknown["min"] is None
    assert unknown["max"] is None


def test_numeric_difficulty_parsing():
    """int 原样、数值字符串转 int、非数值字符串与 None 忽略。"""
    assert _numeric_difficulty(800) == 800
    assert _numeric_difficulty("800") == 800
    assert _numeric_difficulty("hard") is None
    assert _numeric_difficulty(None) is None


def test_difficulty_empty_all_bands_zero():
    bands = difficulty_distribution([])
    assert [b["label"] for b in bands] == [label for label, _mn, _mx in DIFFICULTY_BANDS]
    assert all(b["attemptCount"] == 0 for b in bands)
    assert all(b["submissionCount"] == 0 for b in bands)
    assert all(b["passRate"] == 0.0 for b in bands)


# ===== verdict 分布 =====


def test_verdict_distribution_all_members_and_share():
    items = [
        sub("1", verdict="AC"),
        sub("2", verdict="AC"),
        sub("3", verdict="WA"),
    ]
    dist = verdict_distribution(items)
    assert len(dist) == 9
    assert [d["verdict"] for d in dist] == list(Verdict)
    by = {d["verdict"]: d for d in dist}
    assert by[Verdict.AC]["count"] == 2
    assert by[Verdict.AC]["share"] == round(2 / 3, 4)
    assert by[Verdict.WA]["count"] == 1
    assert by[Verdict.CE]["count"] == 0
    assert by[Verdict.CE]["share"] == 0.0
    assert by[Verdict.JG]["count"] == 0


def test_verdict_distribution_empty():
    dist = verdict_distribution([])
    assert len(dist) == 9
    assert all(d["count"] == 0 for d in dist)
    assert all(d["share"] == 0.0 for d in dist)


# ===== 训练节奏 =====


def test_training_rhythm_weeks_alignment_and_dedup():
    today = datetime.now(TZ).date()
    this_monday = today - timedelta(days=today.weekday())

    def ts_week(week_offset: int, day_offset: int, hour: int = 10) -> int:
        d = this_monday + timedelta(days=week_offset * 7 + day_offset)
        return int(datetime(d.year, d.month, d.day, hour, tzinfo=TZ).timestamp())

    items = [
        sub("1", key="A", verdict="AC", ts=ts_week(0, 0)),
        sub("2", key="A", verdict="AC", ts=ts_week(0, 0)),  # 同题重复 AC
        sub("3", key="B", verdict="WA", ts=ts_week(0, 1)),
        sub("4", key="C", verdict="AC", ts=ts_week(-1, 0)),
        sub("5", key="D", verdict="AC", ts=ts_week(-11, 3)),
        sub("6", key="E", verdict="AC", ts=ts_week(-12, 0)),  # 窗口外
    ]
    weeks = training_rhythm(items, tz=TZ)["weeks"]
    assert len(weeks) == 12
    # 升序，末尾为本周期（本周一）
    assert weeks[-1]["weekStart"] == this_monday.isoformat()
    assert weeks[0]["weekStart"] == (this_monday - timedelta(days=11 * 7)).isoformat()
    # 本周期：A 去重 AC=1、提交 3、活跃 2 天（周一/周二）
    assert weeks[-1]["solved"] == 1
    assert weeks[-1]["attempts"] == 3
    assert weeks[-1]["activeDays"] == 2
    # 上一周期：C 各 1
    assert weeks[-2]["solved"] == 1
    assert weeks[-2]["attempts"] == 1
    assert weeks[-2]["activeDays"] == 1
    # 11 周前：D 各 1
    assert weeks[0]["solved"] == 1
    assert weeks[0]["attempts"] == 1
    # 窗口外提交不计入任何周
    assert sum(w["attempts"] for w in weeks) == 5


def test_training_rhythm_hours():
    today = datetime.now(TZ).date()

    def ts_hour(hour: int) -> int:
        return int(datetime(today.year, today.month, today.day, hour, tzinfo=TZ).timestamp())

    items = [
        sub("1", ts=ts_hour(3)),
        sub("2", ts=ts_hour(3)),
        sub("3", ts=ts_hour(23)),
    ]
    hours = training_rhythm(items, tz=TZ)["hours"]
    assert len(hours) == 24
    assert [h["hour"] for h in hours] == list(range(24))
    assert hours[3]["count"] == 2
    assert hours[23]["count"] == 1
    assert hours[0]["count"] == 0


def test_training_rhythm_custom_weeks():
    out = training_rhythm([], tz=TZ, weeks=3)
    assert len(out["weeks"]) == 3
    assert len(out["hours"]) == 24


# ===== 薄弱点 =====


def test_weak_points_filter_and_sort():
    """attemptCount ≥ 2 才保留；评分 attemptCount*(1-passRate) 降序。"""
    items = [
        sub("1", key="D1", tags=("dp",), verdict="AC"),
        sub("2", key="D2", tags=("dp",), verdict="WA"),
        sub("3", key="D3", tags=("dp",), verdict="WA"),
        sub("4", key="D4", tags=("dp",), verdict="WA"),
        sub("5", key="D5", tags=("dp",), verdict="WA"),
        *[sub(str(6 + i), key=f"G{i}", tags=("greedy",), verdict="WA") for i in range(7)],
        sub("13", key="M1", tags=("math",), verdict="AC"),
        sub("14", key="M2", tags=("math",), verdict="AC"),
        sub("15", key="M3", tags=("math",), verdict="AC"),
        sub("16", key="H1", tags=("graphs",), verdict="WA"),  # 1 尝试 → 过滤
    ]
    wp = weak_points(items)
    assert [w["key"] for w in wp] == ["greedy", "dp", "math"]
    by = {w["key"]: w for w in wp}
    assert by["greedy"]["attemptCount"] == 7
    assert by["greedy"]["solvedCount"] == 0
    assert by["greedy"]["passRate"] == 0.0
    assert by["dp"]["attemptCount"] == 5
    assert by["dp"]["solvedCount"] == 1
    assert by["dp"]["passRate"] == 0.2
    assert by["math"]["passRate"] == 1.0
    assert "graphs" not in by


def test_weak_points_proficiency_matches_skill_tree():
    """薄弱点 proficiency 与技能树口径一致（同源 difficulty_weight + proficiency）。"""
    items = [
        sub("1", key="A", tags=("dp",), difficulty=800),
        sub("2", key="B", tags=("dp",), difficulty=2400),
        sub("3", key="C", tags=("greedy",), difficulty=1200),
    ]
    tree = build_skill_tree(items)
    dp_skill = next(
        s
        for d in tree["domains"]
        if d["key"] == "dynamic_programming"
        for s in d["skills"]
        if s["tag"] == "dp"
    )
    wp = {w["key"]: w for w in weak_points(items)}
    assert wp["dp"]["proficiency"] == dp_skill["proficiency"]
    assert wp["dp"]["maxDifficulty"] == 2400
    assert wp["dp"]["domainKey"] == "dynamic_programming"
    assert wp["dp"]["domainName"] == "动态规划"


def test_weak_points_suggestion_buckets():
    items = [
        sub("1", key="A", tags=("dp",), verdict="WA"),
        sub("2", key="B", tags=("dp",), verdict="WA"),  # 0/2 → <0.3
        sub("3", key="C", tags=("math",), verdict="AC"),
        sub("4", key="D", tags=("math",), verdict="WA"),  # 1/2 → 0.5
        sub("5", key="E", tags=("greedy",), verdict="AC"),
        sub("6", key="F", tags=("greedy",), verdict="AC"),  # 2/2 → 1.0
    ]
    by = {w["key"]: w for w in weak_points(items)}
    assert by["dp"]["suggestion"] == "基础薄弱，建议从该标签入门题系统刷起"
    assert by["math"]["suggestion"] == "有一定基础，建议集中补该标签中等难度题"
    assert by["greedy"]["suggestion"] == "接近熟练，可上难度挑战"


def test_weak_points_unknown_tag_goes_other():
    items = [
        sub("1", key="A", tags=("some-new-tag",), difficulty=1000),
        sub("2", key="B", tags=("some-new-tag",), difficulty=1200),
    ]
    wp = weak_points(items)
    assert len(wp) == 1
    w = wp[0]
    assert w["key"] == "some-new-tag"
    assert w["name"] == "some-new-tag"
    assert w["domainKey"] == "other"
    assert w["domainName"] == "其他"
    assert w["maxDifficulty"] == 1200


def test_weak_points_no_tag_ignored():
    items = [
        sub("1", tags=(), platform="atcoder", difficulty=1000),
        sub("2", tags=(), platform="atcoder", difficulty=1000, verdict="WA"),
    ]
    assert weak_points(items) == []


# ===== 组装 =====


def test_build_analysis_structure():
    out = build_analysis([sub("1", key="A")], tz=TZ)
    assert set(out) == {"difficulty", "verdicts", "rhythm", "weakPoints"}
    assert len(out["difficulty"]) == len(DIFFICULTY_BANDS)
    assert len(out["verdicts"]) == 9
    assert len(out["rhythm"]["weeks"]) == 12
    assert len(out["rhythm"]["hours"]) == 24
    assert isinstance(out["weakPoints"], list)


def test_build_analysis_custom_weeks():
    out = build_analysis([], tz=TZ, weeks=3)
    assert len(out["rhythm"]["weeks"]) == 3
