"""洛谷数据归一化纯函数（无 IO，便于单测）。

状态码与语言码表来自官方前端常量端点 /_lfe/config/auth（2026-08-15 实测
校准），勿凭记忆改写：注意 4=MLE、5=TLE 与直觉相反。
"""

from adapters.base import Verdict

# record.status → 统一 Verdict：
# 0/1 Waiting/Judging → JG（评测中，对齐 CF 的 SUBMITTED/TESTING）；
# 14 Unaccepted → WA（对话确认口径：比赛中未通过本质即未通过评测）；
# 11 UKE、21/22/23 Hack 系列与未知码 → UKE。
VERDICT_MAP: dict[int, Verdict] = {
    0: Verdict.JG,
    1: Verdict.JG,
    2: Verdict.CE,
    3: Verdict.OLE,
    4: Verdict.MLE,
    5: Verdict.TLE,
    6: Verdict.WA,
    7: Verdict.RE,
    12: Verdict.AC,
    14: Verdict.WA,
}


def map_verdict(status: int) -> Verdict:
    """洛谷 record.status 数字码 → 统一 Verdict；未知码归 UKE。"""
    return VERDICT_MAP.get(status, Verdict.UKE)


# record.language → 语言名（官方 CodeLanguage 常量表，id → name）
LANGUAGE_MAP: dict[int, str] = {
    1: "Pascal",
    2: "C",
    3: "C++98",
    4: "C++11",
    5: "提交答案",
    6: "Python 2",
    7: "Python 3",
    8: "Java 8",
    9: "Node.js LTS",
    10: "Shell",
    11: "C++14",
    12: "C++17",
    13: "Ruby",
    14: "Go",
    15: "Rust",
    16: "PHP",
    17: "C# Mono",
    18: "Visual Basic Mono",
    19: "Haskell",
    20: "Kotlin/Native",
    21: "Kotlin/JVM",
    22: "Scala",
    23: "Perl",
    24: "PyPy 2",
    25: "PyPy 3",
    26: "文言",
    27: "C++20",
    28: "C++14 (GCC 9)",
    29: "F#.NET",
    30: "OCaml",
    31: "Julia",
    32: "Lua",
    33: "Java 21",
    34: "C++23",
}


def map_language(language: int) -> str:
    """洛谷 record.language 数字码 → 语言名；未知码兜底空串。"""
    return LANGUAGE_MAP.get(language, "")


def problem_url(pid: str, contest_id: int | None) -> str:
    """题目外链；比赛内提交拼 contestId（clist 格式）；缺 pid 兜底平台主页。"""
    if not pid:
        return "https://www.luogu.com.cn"
    base = f"https://www.luogu.com.cn/problem/{pid}"
    if contest_id is not None:
        return f"{base}?contestId={contest_id}"
    return base
