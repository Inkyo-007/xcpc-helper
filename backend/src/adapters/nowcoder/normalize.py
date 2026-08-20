"""牛客竞赛（NowCoder）数据归一化纯函数（无 IO，便于单测）。"""

from adapters.base import Verdict

# verdict 归一化：牛客状态文本 → 统一 Verdict。
# 经对 330 条真实提交全面扫描确认 8 种状态。
VERDICT_MAP: dict[str, Verdict] = {
    "正在判题": Verdict.JG,
    "答案正确": Verdict.AC,
    "答案错误": Verdict.WA,
    "运行超时": Verdict.TLE,
    "段错误": Verdict.RE,
    "内存超限": Verdict.MLE,
    "输出超限": Verdict.OLE,
    "格式错误": Verdict.WA,  # 牛客的 WA 可能是格式错误
    "内部错误": Verdict.RE,  # 牛客的 RE 可能是内部错误
    "编译错误": Verdict.CE,
    "执行出错": Verdict.RE,  # 通用运行时错误
    "浮点错误": Verdict.RE,  # SIGFPE
    "返回非零": Verdict.RE,  # 非零返回码
    "代码太长": Verdict.CE,  # 代码长度限制
}


def map_verdict(raw: str) -> Verdict:
    """牛客状态文本 → 统一 Verdict；未知结果归 UKE。"""
    return VERDICT_MAP.get(raw, Verdict.UKE)
