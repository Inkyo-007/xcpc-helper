"""QOJ 数据归一化纯函数（无 IO，便于单测）。"""

import re

from adapters.base import Verdict

# verdict 归一化：QOJ 状态文本 → 统一 Verdict。
# 基于对 544 条真实提交的调研分析。
VERDICT_MAP: dict[str, Verdict] = {
    "AC": Verdict.AC,
    "WA": Verdict.WA,
    "RE": Verdict.RE,
    "TL": Verdict.TLE,
    "ML": Verdict.MLE,
    "CE": Verdict.CE,
    "OLE": Verdict.OLE,
    "UKE": Verdict.UKE,
    "JG": Verdict.JG,
}

# 匹配 "100 ✓" / "110 ✓" 等满分通过格式
_FULL_SCORE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*✓$")


def map_verdict(raw: str, score: float | None = None, full_score: float | None = None) -> Verdict:
    """QOJ 状态文本 → 统一 Verdict；未知结果归 UKE。

    处理两类结果：
    1. 明确状态文本（AC ✓/WA/RE/TL/ML 等）
    2. 子任务评分（纯数字，需结合 data-score/data-full 判定）
    """
    text = raw.strip()

    # 情形 A：文本以 ✓ 结尾 → 满分通过（如 "100 ✓" / "110 ✓"）
    if "✓" in text:
        return Verdict.AC

    # 情形 B：文本包含 WA → WA（如 "AC, WA"）
    if "WA" in text:
        return Verdict.WA

    # 情形 C：明确状态文本（2字母缩写）
    if text in VERDICT_MAP:
        return VERDICT_MAP[text]

    # 情形 D：纯数字 → 子任务评分
    try:
        num = float(text)
        # 有 data-full 信息时，满分判定 AC
        if full_score is not None and num >= full_score:
            return Verdict.AC
        # 无 full_score 但数字本身表示满分（如 50 分题得 50）
        # 保守策略：无法确认满分时归 UNAC
        return Verdict.UNAC
    except ValueError:
        pass

    # 兜底：未知结果
    return Verdict.UKE
