"""Codeforces 数据归一化纯函数（无 IO，便于单测）。"""

from adapters.base import Verdict

# verdict 归一化：OK→AC 等；未列出的（CHALLENGED / SKIPPED / PARTIAL /
# FAILED / CRASHED / IDLENESS_LIMIT_EXCEEDED / INPUT_PREPARATION_CRASHED 等）
# 一律归 UKE；SUBMITTED / TESTING 归 JG（评测中）。
VERDICT_MAP: dict[str, Verdict] = {
    "OK": Verdict.AC,
    "WRONG_ANSWER": Verdict.WA,
    "COMPILATION_ERROR": Verdict.CE,
    "RUNTIME_ERROR": Verdict.RE,
    "TIME_LIMIT_EXCEEDED": Verdict.TLE,
    "MEMORY_LIMIT_EXCEEDED": Verdict.MLE,
    "SUBMITTED": Verdict.JG,
    "TESTING": Verdict.JG,
}


def map_verdict(raw: str) -> Verdict:
    """CF verdict 文本 → 统一 Verdict；未知结果归 UKE。"""
    return VERDICT_MAP.get(raw, Verdict.UKE)


def problem_url(contest_id: int | None, index: str | None) -> str:
    """题目外链；缺 contestId / index 时兜底平台主页。"""
    if contest_id is not None and index:
        return f"https://codeforces.com/problemset/problem/{contest_id}/{index}"
    return "https://codeforces.com"


def problem_key(contest_id: int | None, index: str | None, name: str) -> str:
    """平台内题目标识：contestId + index（如 2245F）；缺失时退化为题名。"""
    if contest_id is not None and index:
        return f"{contest_id}{index}"
    return name or "?"
