"""AtCoder 数据归一化纯函数（无 IO，便于单测）。"""

from adapters.base import Verdict

# verdict 归一化：AtCoder result 文本 → 统一 Verdict。
# AC/WA/TLE/MLE/RE/CE/OLE 直映射；WJ/WR/JUDGING 归 JG（评测中，对齐 CF 的
# SUBMITTED/TESTING）；IE/QLE 与未列出的值一律归 UKE。
VERDICT_MAP: dict[str, Verdict] = {
    "AC": Verdict.AC,
    "WA": Verdict.WA,
    "TLE": Verdict.TLE,
    "MLE": Verdict.MLE,
    "RE": Verdict.RE,
    "CE": Verdict.CE,
    "OLE": Verdict.OLE,
    "WJ": Verdict.JG,
    "WR": Verdict.JG,
    "JUDGING": Verdict.JG,
}


def map_verdict(raw: str) -> Verdict:
    """AtCoder result 文本 → 统一 Verdict；未知结果归 UKE。"""
    return VERDICT_MAP.get(raw, Verdict.UKE)


def problem_url(contest_id: str, problem_id: str) -> str:
    """题目外链；缺 contest_id / problem_id 时兜底平台主页。"""
    if contest_id and problem_id:
        return f"https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}"
    return "https://atcoder.jp"
