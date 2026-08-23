"""LeetCode CN 归一化纯函数。"""

from adapters.base import Verdict


def map_verdict(status_display: str) -> Verdict:
    """submissionList.statusDisplay → 归一化 Verdict。"""
    mapping = {
        "Accepted": Verdict.AC,
        "Wrong Answer": Verdict.WA,
        "Runtime Error": Verdict.RE,
        "Compile Error": Verdict.CE,
        "Time Limit Exceeded": Verdict.TLE,
        "Memory Limit Exceeded": Verdict.MLE,
        "Output Limit Exceeded": Verdict.OLE,
    }
    return mapping.get(status_display, Verdict.UKE)


def problem_url(title_slug: str) -> str:
    """生成题目外链。"""
    return f"https://leetcode.cn/problems/{title_slug}/"
