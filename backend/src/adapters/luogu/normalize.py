"""洛谷数据归一化纯函数（无 IO，便于单测）。

状态码与语言码表来自官方前端常量端点 /_lfe/config/auth（2026-08-15 实测
校准），勿凭记忆改写：注意 4=MLE、5=TLE 与直觉相反。
"""

from adapters.base import Verdict

# record.status → 统一 Verdict：
# 0/1 Waiting/Judging → JG（评测中，对齐 CF 的 SUBMITTED/TESTING）；
# 14 Unaccepted → UNAC（列表口径结构性无细分——filterable 仅 2/12/14 可筛，
# WA/TLE/MLE/RE 只在记录详情测试点信息中，逐条拉取成本不可接受）；
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
    14: Verdict.UNAC,
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


# ===== UNAC 精化：测试点状态 → 细分 verdict =====

# 可参选的状态码（可归因于用户程序的错误）→ 统一 Verdict；
# JG（0/1）/UKE（11）不参选（评测中方/评测方故障），CE 不经精化，
# AC（12）为通过不参与比较。
_ELIGIBLE: dict[int, Verdict] = {
    6: Verdict.WA,
    7: Verdict.RE,
    5: Verdict.TLE,
    4: Verdict.MLE,
    3: Verdict.OLE,
}

# 严重度优先级（对话确认）：RE > TLE > MLE > OLE > WA
_SEVERITY: dict[Verdict, int] = {
    Verdict.RE: 4,
    Verdict.TLE: 3,
    Verdict.MLE: 2,
    Verdict.OLE: 1,
    Verdict.WA: 0,
}


def pick_verdict(case_statuses: list[int]) -> Verdict | None:
    """测试点状态码列表 → 细分 verdict。

    两级判定：
    1. 参选集合（WA/RE/TLE/MLE/OLE，可归因于用户程序）中取严重度最重者；
    2. 无参选但存在 UKE 测点 → UKE（记录确实遭遇评测方故障；实测存在
       纯 UKE / UKE+AC 混合形态，见 activity/luogu.md）；
    3. 全 AC / 仅 JG / 空列表 → None（保持 UNAC，调用方打 attempted 标记
       终止重试，防重试循环）。
    """
    best: Verdict | None = None
    has_uke = False
    for status in case_statuses:
        verdict = _ELIGIBLE.get(status)
        if verdict is None:
            if status == 11:
                has_uke = True
            continue
        if best is None or _SEVERITY[verdict] > _SEVERITY[best]:
            best = verdict
    if best is not None:
        return best
    return Verdict.UKE if has_uke else None


def problem_url(pid: str, contest_id: int | None) -> str:
    """题目外链；比赛内提交拼 contestId（clist 格式）；缺 pid 兜底平台主页。"""
    if not pid:
        return "https://www.luogu.com.cn"
    base = f"https://www.luogu.com.cn/problem/{pid}"
    if contest_id is not None:
        return f"{base}?contestId={contest_id}"
    return base
