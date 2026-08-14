"""四维训练分析聚合纯函数（无 IO）：难度分布 / verdict 分布 / 训练节奏 / 薄弱点。

契约见 docs/design/analysis.md §3。要点：
- 难度分布按「去重题目 (platform, problem_key)」分档，难度取该题提交的最大数值难度，
  非数值难度（None / 非数值字符串）归「未知」档；全档位恒返回；
- verdict 分布按 Verdict 枚举声明顺序全量输出（含 0 计数）；
- 训练节奏按本地时区切周 / 小时：近 weeks 周（含本周，升序，末尾为本周期）；
- 薄弱点只统计带标签的提交，复用 skill_tree 的标签→域映射与 proficiency 公式，
  口径与技能树一致；按「投入多、通过少」评分降序，仅保留 attemptCount ≥ 2 的技能。
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta, tzinfo

from adapters.base import Verdict
from modules.activity.models import Submission
from modules.activity.skill_tree import (
    DOMAIN_ORDER,
    OTHER_DOMAIN_KEY,
    OTHER_DOMAIN_NAME,
    TAG_NAME,
    TAG_TO_DOMAIN,
    difficulty_weight,
    proficiency,
)

# 难度分档（顺序输出；min/max 为 None 表示无下界/上界，末档「未知」仅由非数值难度进入）
DIFFICULTY_BANDS: list[tuple[str, int | None, int | None]] = [
    ("≤1199", None, 1199),
    ("1200–1399", 1200, 1399),
    ("1400–1599", 1400, 1599),
    ("1600–1799", 1600, 1799),
    ("1800–1999", 1800, 1999),
    ("2000–2199", 2000, 2199),
    ("2200–2399", 2200, 2399),
    ("2400–2599", 2400, 2599),
    ("2600+", 2600, None),
    ("未知", None, None),
]

_UNKNOWN_INDEX = len(DIFFICULTY_BANDS) - 1


def _numeric_difficulty(difficulty: int | str | None) -> int | None:
    """难度 → 数值：int 原样；数值字符串转 int；None / 非数值字符串返回 None。"""
    if isinstance(difficulty, int):
        return difficulty
    if isinstance(difficulty, str):
        try:
            return int(difficulty)
        except ValueError:
            return None
    return None


def _max_numeric(a: int | None, b: int | None) -> int | None:
    """两可空数值取较大者（None 视为缺失，不参与比较）。"""
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _band_index(diff: int) -> int:
    """数值难度 → 分档下标（跳过「未知」档）。"""
    for i, (_label, mn, mx) in enumerate(DIFFICULTY_BANDS):
        if mn is None and mx is None:
            continue  # 未知档仅由非数值难度进入
        if (mn is None or diff >= mn) and (mx is None or diff <= mx):
            return i
    return _UNKNOWN_INDEX  # 理论上不可达（分档已覆盖全部整数）


def _local_date(ts: int, tz: tzinfo) -> date:
    return datetime.fromtimestamp(ts, tz=tz).date()


def difficulty_distribution(
    submissions: Iterable[Submission],
) -> list[dict[str, object]]:
    """按去重题目 (platform, problem_key) 聚合的难度分档统计（全档位恒返回）。"""
    per_problem: dict[tuple[str, str], tuple[int | None, bool, int]] = {}
    for s in submissions:
        key = (s.platform, s.problem_key)
        diff = _numeric_difficulty(s.difficulty)
        is_ac = s.verdict == Verdict.AC
        if key in per_problem:
            prev_diff, prev_ac, prev_count = per_problem[key]
            per_problem[key] = (
                _max_numeric(prev_diff, diff),
                prev_ac or is_ac,
                prev_count + 1,
            )
        else:
            per_problem[key] = (diff, is_ac, 1)

    solved = [0] * len(DIFFICULTY_BANDS)
    attempted = [0] * len(DIFFICULTY_BANDS)
    submitted = [0] * len(DIFFICULTY_BANDS)
    for diff, is_ac, count in per_problem.values():
        idx = _band_index(diff) if diff is not None else _UNKNOWN_INDEX
        attempted[idx] += 1
        submitted[idx] += count
        if is_ac:
            solved[idx] += 1

    out: list[dict[str, object]] = []
    for i, (label, mn, mx) in enumerate(DIFFICULTY_BANDS):
        attempt_count = attempted[i]
        out.append(
            {
                "label": label,
                "min": mn,
                "max": mx,
                "solvedCount": solved[i],
                "attemptCount": attempt_count,
                "submissionCount": submitted[i],
                "passRate": round(solved[i] / attempt_count, 4) if attempt_count else 0.0,
            }
        )
    return out


def verdict_distribution(
    submissions: Iterable[Submission],
) -> list[dict[str, object]]:
    """按 Verdict 枚举声明顺序统计提交计数与占比（全 9 个成员恒返回）。"""
    counts: dict[Verdict, int] = {v: 0 for v in Verdict}
    total = 0
    for s in submissions:
        counts[s.verdict] += 1
        total += 1

    out: list[dict[str, object]] = []
    for v in Verdict:
        count = counts[v]
        out.append(
            {
                "verdict": v,
                "count": count,
                "share": round(count / total, 4) if total else 0.0,
            }
        )
    return out


def training_rhythm(
    submissions: Iterable[Submission],
    *,
    tz: tzinfo,
    weeks: int = 12,
) -> dict[str, object]:
    """近 weeks 周（含本周，升序）节奏 + 0..23 小时提交数（本地时区）。"""
    today = datetime.now(tz=tz).date()
    this_monday = today - timedelta(days=today.weekday())
    earliest = this_monday - timedelta(days=(weeks - 1) * 7)

    attempts: dict[int, int] = {}
    solved_keys: dict[int, set[tuple[str, str]]] = {}
    active_days: dict[int, set[date]] = {}
    for s in submissions:
        d = _local_date(s.submitted_at, tz)
        offset_days = (d - earliest).days
        if not 0 <= offset_days < weeks * 7:
            continue
        idx = offset_days // 7
        attempts[idx] = attempts.get(idx, 0) + 1
        active_days.setdefault(idx, set()).add(d)
        if s.verdict == Verdict.AC:
            solved_keys.setdefault(idx, set()).add((s.platform, s.problem_key))

    weeks_out: list[dict[str, object]] = []
    for i in range(weeks):
        start = this_monday - timedelta(days=(weeks - 1 - i) * 7)
        weeks_out.append(
            {
                "weekStart": start.isoformat(),
                "solved": len(solved_keys.get(i, set())),
                "attempts": attempts.get(i, 0),
                "activeDays": len(active_days.get(i, set())),
            }
        )

    hours: list[dict[str, int]] = [{"hour": h, "count": 0} for h in range(24)]
    for s in submissions:
        hours[datetime.fromtimestamp(s.submitted_at, tz=tz).hour]["count"] += 1

    return {"weeks": weeks_out, "hours": hours}


def _suggestion(pass_rate: float) -> str:
    """按通过率给出规则化训练建议。"""
    if pass_rate < 0.3:
        return "基础薄弱，建议从该标签入门题系统刷起"
    if pass_rate < 0.6:
        return "有一定基础，建议集中补该标签中等难度题"
    return "接近熟练，可上难度挑战"


def _domain_name(domain_key: str) -> str:
    """域 key → 中文名（未命中 DOMAIN_ORDER 归「其他」）。"""
    for key, name in DOMAIN_ORDER:
        if key == domain_key:
            return name
    return OTHER_DOMAIN_NAME


def weak_points(submissions: Iterable[Submission]) -> list[dict[str, object]]:
    """带标签提交 → 技能薄弱点（复用技能树标签映射与 proficiency 口径）。"""
    tag_attempts: dict[str, set[tuple[str, str]]] = defaultdict(set)
    tag_solved: dict[str, set[tuple[str, str]]] = defaultdict(set)
    solved_diff: dict[tuple[str, str], int | None] = {}

    for s in submissions:
        tags = set(s.tags or [])
        if not tags:
            continue
        key = (s.platform, s.problem_key)
        for tag in tags:
            tag_attempts[tag].add(key)
        if s.verdict == Verdict.AC:
            for tag in tags:
                tag_solved[tag].add(key)
            solved_diff[key] = _max_numeric(
                solved_diff.get(key), _numeric_difficulty(s.difficulty)
            )

    scored: list[tuple[float, str, dict[str, object]]] = []
    for tag in tag_attempts:
        attempt_count = len(tag_attempts[tag])
        if attempt_count < 2:
            continue
        solved_keys = tag_solved.get(tag, set())
        solved_count = len(solved_keys)
        pass_rate = round(solved_count / attempt_count, 4)
        weights = [difficulty_weight(solved_diff[k]) for k in solved_keys]
        difficulties = [
            solved_diff[k] for k in solved_keys if solved_diff[k] is not None
        ]
        domain_key = TAG_TO_DOMAIN.get(tag, OTHER_DOMAIN_KEY)
        score = attempt_count * (1 - pass_rate)
        scored.append(
            (
                score,
                tag,
                {
                    "key": tag,
                    "name": TAG_NAME.get(tag, tag),
                    "domainKey": domain_key,
                    "domainName": _domain_name(domain_key),
                    "solvedCount": solved_count,
                    "attemptCount": attempt_count,
                    "passRate": pass_rate,
                    "proficiency": proficiency(weights),
                    "maxDifficulty": max(difficulties) if difficulties else None,
                    "suggestion": _suggestion(pass_rate),
                },
            )
        )

    # 弱点评分降序、并列按 key 升序；取前 20 条
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [item for _score, _key, item in scored[:20]]


def build_analysis(
    submissions: Iterable[Submission],
    *,
    tz: tzinfo,
    weeks: int = 12,
) -> dict[str, object]:
    """四维聚合（difficulty / verdicts / rhythm / weakPoints），无 IO。"""
    items = list(submissions)
    return {
        "difficulty": difficulty_distribution(items),
        "verdicts": verdict_distribution(items),
        "rhythm": training_rhythm(items, tz=tz, weeks=weeks),
        "weakPoints": weak_points(items),
    }
