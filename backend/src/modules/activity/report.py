"""在线 LLM 分析报告纯函数（无 IO）：prompt 组装与规则化降级报告。

契约见 docs/design/analysis.md §5。要点：
- build_prompt：把四维聚合 analysis 与 overview 总量用紧凑 JSON 序列化进 user
  消息，system 消息设定中文竞赛教练人设与输出要求；
- build_rule_report：纯规则生成中文 Markdown 报告，全部文案从数据推导、确定性
  强，供 LLM 未配置或调用失败时降级使用（离线零依赖）。
"""

import json

from adapters.base import Verdict

# 提交质量提示阈值：超过即认为该错误类型偏高（规则化文案，确定性）
_WA_HIGH_SHARE = 0.2
_TLE_HIGH_SHARE = 0.1
# 难度档位 passRate 低于该值视为「较低」，值得提示补强
_LOW_PASS_RATE = 0.5

# 空数据/不足 3 条薄弱点时的兜底建议（通用、可执行）
_FALLBACK_SUGGESTIONS: list[str] = [
    "制定每日固定训练时段，保持稳定刷题节奏。",
    "从入门难度开始逐档提升，先建立稳定的 AC 正反馈。",
    "每道题写题解与复盘，沉淀常见错误类型。",
]


def _verdict_value(v: object) -> str:
    """verdict 归一为字符串代码（枚举取 value，其余直接转字符串）。"""
    if isinstance(v, Verdict):
        return v.value
    return str(v)


def _pct(value: float) -> str:
    """0..1 数值 → 百分比字符串（如 0.25 → '25%'）。"""
    return f"{value:.0%}"


def build_prompt(analysis: dict, overview: dict) -> list[dict]:
    """组装 OpenAI chat 消息列表：system 人设 + user 紧凑 JSON 数据摘要。"""
    system_msg = (
        "你是一名资深算法竞赛（XCPC）教练，擅长依据训练数据给出针对性诊断与训练建议。"
        "请基于用户提供的训练统计数据，生成一份中文 Markdown 分析报告："
        "要有清晰的标题与分节、结论必须可执行、不得编造数据、只基于给定数据陈述。"
    )
    compact = json.dumps(
        {"analysis": analysis, "overview": overview},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    user_msg = (
        "以下是我的训练统计数据（JSON，请据此生成中文 Markdown 分析报告）：\n"
        + compact
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def build_rule_report(analysis: dict, overview: dict) -> str:
    """纯规则生成中文 Markdown 报告（总体概况/难度/质量/节奏/薄弱点/建议）。"""
    difficulty = analysis.get("difficulty") or []
    verdicts = analysis.get("verdicts") or []
    rhythm = analysis.get("rhythm") or {}
    weeks = rhythm.get("weeks") or []
    hours = rhythm.get("hours") or []
    weak_points = analysis.get("weakPoints") or []

    total_solved = int(overview.get("totalSolved", 0))
    total_submissions = int(overview.get("totalSubmissions", 0))
    today_solved = int(overview.get("todaySolved", 0))
    week_solved = int(overview.get("weekSolved", 0))
    streak_days = int(overview.get("streakDays", 0))

    # ===== 提交质量（verdict 占比） =====
    by_verdict = {_verdict_value(v.get("verdict")): v for v in verdicts}
    ac = by_verdict.get("AC", {})
    wa = by_verdict.get("WA", {})
    tle = by_verdict.get("TLE", {})
    ac_share = float(ac.get("share", 0))
    wa_share = float(wa.get("share", 0))
    tle_share = float(tle.get("share", 0))

    # ===== 难度分布（主力分档 + passRate 较低的档） =====
    attempted = [b for b in difficulty if int(b.get("attemptCount", 0)) > 0]
    low_bands = sorted(
        [b for b in attempted if float(b.get("passRate", 0)) < _LOW_PASS_RATE],
        key=lambda b: float(b.get("passRate", 0)),
    )[:3]

    # ===== 训练节奏（近 12 周趋势） =====
    week_attempts = [int(w.get("attempts", 0)) for w in weeks]
    attempts_total = sum(week_attempts)
    active_weeks = sum(1 for a in week_attempts if a > 0)
    recent = sum(week_attempts[-4:])
    earlier = sum(week_attempts[:-4])

    lines: list[str] = ["# 训练分析报告", ""]

    # ===== 总体概况 =====
    lines.append("## 总体概况")
    lines.append("")
    lines.append(f"- 累计解题：**{total_solved}** 题（去重 AC）")
    lines.append(f"- 累计提交：**{total_submissions}** 次")
    lines.append(f"- 今日解题：{today_solved} 题；近 7 天解题：{week_solved} 题")
    lines.append(f"- 连续活跃：{streak_days} 天")
    lines.append("")

    # ===== 难度分布解读 =====
    lines.append("## 难度分布解读")
    lines.append("")
    if not attempted:
        lines.append("- 暂无难度分布数据。")
    else:
        main_band = max(attempted, key=lambda b: int(b.get("attemptCount", 0)))
        lines.append(
            f"- 主力分档：**{main_band.get('label')}**"
            f"（尝试 {int(main_band.get('attemptCount', 0))} 题、"
            f"通过率 {_pct(float(main_band.get('passRate', 0)))}）。"
        )
        if low_bands:
            names = "、".join(
                f"{b.get('label')}（{_pct(float(b.get('passRate', 0)))}）"
                for b in low_bands
            )
            lines.append(f"- 通过率较低的档位：{names}，建议针对性补强。")
        else:
            lines.append("- 各档位通过率整体健康。")
    lines.append("")

    # ===== 提交质量 =====
    lines.append("## 提交质量")
    lines.append("")
    if total_submissions == 0:
        lines.append("- 暂无提交数据。")
    else:
        lines.append(f"- AC 占比：**{_pct(ac_share)}**（{int(ac.get('count', 0))} 次）")
        lines.append(f"- WA 占比：{_pct(wa_share)}（{int(wa.get('count', 0))} 次）")
        lines.append(f"- TLE 占比：{_pct(tle_share)}（{int(tle.get('count', 0))} 次）")
        if wa_share >= _WA_HIGH_SHARE:
            lines.append("- ⚠️ WA 占比较高，建议提交前多造边界样例、本地对拍验证。")
        if tle_share >= _TLE_HIGH_SHARE:
            lines.append("- ⚠️ TLE 占比较高，建议关注时间复杂度与剪枝优化。")
    lines.append("")

    # ===== 训练节奏 =====
    lines.append("## 训练节奏")
    lines.append("")
    if not weeks:
        lines.append("- 暂无训练节奏数据。")
    else:
        lines.append(f"- 近 12 周共提交 **{attempts_total}** 次，活跃 **{active_weeks}** 周。")
        if recent == 0:
            trend = "近 4 周无提交，训练可能中断，建议尽快恢复节奏。"
        elif earlier == 0:
            trend = "近 4 周开始有提交，训练已起步，保持下去。"
        elif recent >= earlier * 1.2:
            trend = "近 4 周提交量上升，训练节奏向好。"
        elif recent <= earlier * 0.8:
            trend = "近 4 周提交量下降，注意保持稳定节奏。"
        else:
            trend = "训练节奏整体平稳。"
        lines.append(f"- 趋势：{trend}")
    hour_counts = [int(h.get("count", 0)) for h in hours]
    if hour_counts and max(hour_counts) > 0:
        peak = max(hour_counts)
        peak_hours = [i for i, c in enumerate(hour_counts) if c == peak]
        labels = "、".join(f"{h} 时" for h in peak_hours)
        lines.append(f"- 活跃时段集中在 {labels}（各 {peak} 次提交）。")
    else:
        lines.append("- 暂无活跃时段数据。")
    lines.append("")

    # ===== 薄弱点清单 =====
    lines.append("## 薄弱点清单")
    lines.append("")
    if not weak_points:
        lines.append("- 暂无薄弱点数据（需至少 2 次尝试的带标签提交）。")
    else:
        for wp in weak_points:
            name = wp.get("name")
            pass_rate = float(wp.get("passRate", 0))
            proficiency = float(wp.get("proficiency", 0))
            suggestion = wp.get("suggestion", "")
            lines.append(
                f"- **{name}**：通过率 {_pct(pass_rate)}，掌握度 {_pct(proficiency)}。"
                f"{suggestion}"
            )
    lines.append("")

    # ===== 下一步建议（基于薄弱点 top，最多 3 条可执行建议） =====
    lines.append("## 下一步建议")
    lines.append("")
    candidates: list[str] = []
    for wp in weak_points[:3]:
        candidates.append(
            f"针对「{wp.get('name')}」（通过率 {_pct(float(wp.get('passRate', 0)))}）："
            f"{wp.get('suggestion', '')}"
        )
    if wa_share >= _WA_HIGH_SHARE:
        candidates.append("针对 WA 偏高：建立提交前自测清单（样例、边界、对拍）。")
    if tle_share >= _TLE_HIGH_SHARE:
        candidates.append("针对 TLE 偏高：复盘复杂度，练习剪枝与更优算法。")
    if low_bands:
        labels = "、".join(str(b.get("label")) for b in low_bands)
        candidates.append(f"针对通过率较低的难度档（{labels}）：从该档位入门题系统补强。")
    if recent == 0 and total_submissions > 0:
        candidates.append("训练节奏中断：尽快恢复每周稳定提交。")
    candidates.extend(_FALLBACK_SUGGESTIONS)

    # 去重保序后取前 3 条
    seen: set[str] = set()
    deduped: list[str] = []
    for s in candidates:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    for i, s in enumerate(deduped[:3], 1):
        lines.append(f"{i}. {s}")
    lines.append("")

    return "\n".join(lines)
