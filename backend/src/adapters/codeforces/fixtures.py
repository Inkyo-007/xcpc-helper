"""Codeforces 数据归一化纯函数（无 IO，便于单测）。"""

import re

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
    """题目外链；缺 contestId / index 时兜底平台主页。

    CF 主题库与 gym 题库的 URL 形式不同，按 contest_id 位数区分：
    主题库一般为四位数（/contest/ 页），gym 一般为六位数（/gym/ 页）。
    """
    if contest_id is not None and index:
        if contest_id >= 100000:
            return f"https://codeforces.com/gym/{contest_id}/problem/{index}"
        return f"https://codeforces.com/contest/{contest_id}/problem/{index}"
    return "https://codeforces.com"


# 旧格式（problemset/problem/<contest_id>/<index>）识别用
_PROBLEMSET_URL_RE = re.compile(
    r"^https://codeforces\.com/problemset/problem/(\d+)/([A-Za-z0-9_]+)$"
)


def normalize_problem_url(url: str) -> str:
    """把旧格式 problemset 链接幂等转换为新格式（contest/gym）。

    新格式链接与无法识别的链接原样返回；用于读取旧数据时迁移，
    无需重新同步即可让历史提交显示正确外链。
    """
    m = _PROBLEMSET_URL_RE.match(url)
    if not m:
        return url
    return problem_url(int(m.group(1)), m.group(2))


def problem_key(contest_id: int | None, index: str | None, name: str) -> str:
    """平台内题目标识：contestId + index（如 2245F）；缺失时退化为题名。"""
    if contest_id is not None and index:
        return f"{contest_id}{index}"
    return name or "?"
