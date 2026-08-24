"""VJudge 数据归一化纯函数（无 IO，便于单测）。"""

from adapters.base import Verdict

# verdict 归一化：VJudge status 字段 → 统一 Verdict。
# 注意：/status/data 返回的 status 为完整字符串（如 "Accepted"），
# 与旧 /user/submissions 的缩写（如 "AC"）不同。
VERDICT_MAP: dict[str, Verdict] = {
    # 精确匹配（/status/data 的完整字符串）
    "Accepted": Verdict.AC,
    "Wrong Answer": Verdict.WA,
    "Time Limit Exceeded": Verdict.TLE,
    "Memory Limit Exceeded": Verdict.MLE,
    "Runtime Error": Verdict.RE,
    "Compilation Error": Verdict.CE,
    "Output Limit Exceeded": Verdict.OLE,
    "Presentation Error": Verdict.WA,
    # 缩写形式（兼容旧接口，防御性）
    "AC": Verdict.AC,
    "WA": Verdict.WA,
    "TLE": Verdict.TLE,
    "MLE": Verdict.MLE,
    "RE": Verdict.RE,
    "CE": Verdict.CE,
    "OLE": Verdict.OLE,
    "PE": Verdict.WA,
    # 评测中状态
    "Judging": Verdict.JG,
    "Pending": Verdict.JG,
    "Running": Verdict.JG,
    "Compiling": Verdict.JG,
    "Waiting": Verdict.JG,
    "In Queue": Verdict.JG,
}


def map_verdict(raw: str) -> Verdict:
    """VJudge status 字段 → 统一 Verdict；未知结果归 UKE。"""
    if not raw:
        return Verdict.UKE
    return VERDICT_MAP.get(raw, Verdict.UKE)


def problem_url(oj_id: str, prob_num: str) -> str:
    """生成题目外链。"""
    return f"https://vjudge.net/problem/{oj_id}-{prob_num}"
