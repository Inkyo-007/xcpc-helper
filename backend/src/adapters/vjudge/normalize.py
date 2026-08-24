"""VJudge 数据归一化纯函数（无 IO，便于单测）。"""

from adapters.base import Verdict

# verdict 归一化：VJudge result 字段 → 统一 Verdict。
VERDICT_MAP: dict[str, Verdict] = {
    "AC": Verdict.AC,
    "WA": Verdict.WA,
    "TLE": Verdict.TLE,
    "MLE": Verdict.MLE,
    "RE": Verdict.RE,
    "CE": Verdict.CE,
    "OLE": Verdict.OLE,
    "PE": Verdict.UKE,
    "JUDGING": Verdict.JG,
    "PENDING": Verdict.JG,
    "RUNNING": Verdict.JG,
    "COMPILING": Verdict.JG,
    "WAITING": Verdict.JG,
}


def map_verdict(raw: str) -> Verdict:
    """VJudge result 字段 → 统一 Verdict；未知结果归 UKE。"""
    return VERDICT_MAP.get(raw.upper(), Verdict.UKE)


def problem_url(oj_id: str, prob_num: str) -> str:
    """生成题目外链。"""
    return f"https://vjudge.net/problem/{oj_id}-{prob_num}"
