/** 训练分析可视化（纯函数）：把四维聚合数据换算为 ECharts option 与展示分组。
 * DOM 无关、可单测；图表颜色来自主题桥接的调色板（见 echarts-theme.ts），
 * 唯一例外是 verdict 语义色（固定，与活动页徽章一致，见 components/SubmissionList.vue）。
 */

import type { ChartPalette } from '@/features/activity/model/echarts-theme'
import type { EChartsCoreOption } from '@/features/activity/model/echarts-setup'
import type {
  DifficultyBand,
  HourActivity,
  Rhythm,
  Verdict,
  VerdictCount,
  WeakPoint,
} from '@/features/activity/types'

/** 0~1 比值 → 百分比文案（掌握度 / 通过率共用） */
export function percentText(ratio: number): string {
  return `${Math.round(ratio * 100)}%`
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/* ---------- verdict 语义色（固定，不随主题变化） ---------- */

/** verdict 徽章固定配色：AC 绿 / WA 红 / CE 黄 / RE 紫 / JG 浅蓝 / 资源超限与未知深蓝 */
const VERDICT_COLORS: Record<Verdict, string> = {
  AC: '#1e9e52',
  WA: '#d64541',
  CE: '#c28a0a',
  RE: '#8a5cf0',
  JG: '#2b8fc8',
  TLE: '#2f5fc7',
  MLE: '#2f5fc7',
  OLE: '#2f5fc7',
  UKE: '#2f5fc7',
}

export function verdictColor(verdict: Verdict): string {
  return VERDICT_COLORS[verdict]
}

/** 全部 verdict 的提交总数（过滤前口径，与后端 total 一致） */
export function totalSubmissions(verdicts: VerdictCount[]): number {
  return verdicts.reduce((sum, v) => sum + v.count, 0)
}

/* ---------- 难度分布：横向条形图（通过 / 尝试双系列） ---------- */

interface AxisTooltipParam {
  seriesName: string
  value: number
  dataIndex: number
}

export function buildDifficultyOption(
  bands: DifficultyBand[],
  palette: ChartPalette,
): EChartsCoreOption {
  return {
    grid: { left: 4, right: 16, top: 28, bottom: 2, containLabel: true },
    legend: {
      data: ['通过', '尝试'],
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: palette.faint, fontSize: 11 },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: palette.tooltipBg,
      borderWidth: 0,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      extraCssText:
        'border-radius:8px;padding:7px 11px;box-shadow:0 6px 20px rgb(20 16 10 / 0.25);',
      formatter: (params: AxisTooltipParam[]) => {
        const band = bands[params[0]?.dataIndex ?? -1]
        if (!band) return ''
        const rows = params
          .map((p) => `${escapeHtml(p.seriesName)} · ${p.value} 题`)
          .join('<br>')
        return (
          `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(band.label)}</div>` +
          `<div style="opacity:.85;font-size:11px">${rows}<br>通过率 ${percentText(band.passRate)}</div>`
        )
      },
    },
    xAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: palette.border, type: 'dashed' } },
      axisLabel: { color: palette.faint, fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      data: bands.map((b) => b.label),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: palette.text, fontSize: 11 },
    },
    series: [
      {
        name: '尝试',
        type: 'bar',
        data: bands.map((b) => b.attemptCount),
        barMaxWidth: 14,
        itemStyle: { color: palette.heatColors[3], borderRadius: [0, 4, 4, 0] },
      },
      {
        name: '通过',
        type: 'bar',
        data: bands.map((b) => b.solvedCount),
        barMaxWidth: 14,
        itemStyle: { color: palette.accent, borderRadius: [0, 4, 4, 0] },
      },
    ],
  }
}

/* ---------- 提交质量：verdict 环形饼图（中心显示总提交数） ---------- */

export function buildVerdictOption(
  verdicts: VerdictCount[],
  palette: ChartPalette,
): EChartsCoreOption {
  const items = verdicts.filter((v) => v.count > 0)
  const total = totalSubmissions(verdicts)
  return {
    color: items.map((v) => verdictColor(v.verdict)),
    tooltip: {
      trigger: 'item',
      backgroundColor: palette.tooltipBg,
      borderWidth: 0,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      extraCssText:
        'border-radius:8px;padding:7px 11px;box-shadow:0 6px 20px rgb(20 16 10 / 0.25);',
      formatter: (params: { name?: string; value?: number; percent?: number }) => {
        if (params.name == null) return ''
        return (
          `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(params.name)}</div>` +
          `<div style="opacity:.85;font-size:11px">${params.value ?? 0} 次 · 占比 ${Math.round(params.percent ?? 0)}%</div>`
        )
      },
    },
    legend: {
      orient: 'vertical',
      right: 0,
      top: 'middle',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: palette.faint, fontSize: 11 },
    },
    title: {
      text: String(total),
      subtext: '总提交',
      left: '42%',
      top: 'middle',
      textAlign: 'center',
      textStyle: { color: palette.text, fontSize: 22, fontWeight: 700 },
      subtextStyle: { color: palette.faint, fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['46%', '70%'],
        center: ['42%', '50%'],
        itemStyle: { borderColor: palette.surface, borderWidth: 2 },
        label: { show: false },
        data: items.map((v) => ({
          name: v.verdict,
          value: v.count,
          itemStyle: { color: verdictColor(v.verdict) },
        })),
      },
    ],
  }
}

/* ---------- 训练节奏：近 12 周柱状图 + 活跃时段柱状图（单 option 双 grid） ---------- */

/** 0~23 小时提交数归一化为 24 长度数组（缺失小时补 0） */
function hourCounts(hours: HourActivity[]): number[] {
  const byHour = new Map<number, number>()
  for (const h of hours) byHour.set(h.hour, h.count)
  return Array.from({ length: 24 }, (_, hour) => byHour.get(hour) ?? 0)
}

/** 周标签：weekStart（YYYY-MM-DD）→ MM-DD */
function weekLabel(weekStart: string): string {
  return weekStart.slice(5)
}

export function buildRhythmOption(rhythm: Rhythm, palette: ChartPalette): EChartsCoreOption {
  const weeks = rhythm.weeks
  const hours = hourCounts(rhythm.hours)
  const hourLabels = Array.from({ length: 24 }, (_, h) => `${h}`)
  return {
    grid: [
      { left: 4, right: 16, top: 28, height: '44%', containLabel: true },
      { left: 4, right: 16, top: '62%', bottom: 2, containLabel: true },
    ],
    legend: {
      data: ['通过', '提交'],
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: palette.faint, fontSize: 11 },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: palette.tooltipBg,
      borderWidth: 0,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      extraCssText:
        'border-radius:8px;padding:7px 11px;box-shadow:0 6px 20px rgb(20 16 10 / 0.25);',
      formatter: (params: { seriesName?: string; dataIndex?: number; value?: number }) => {
        const idx = params.dataIndex ?? -1
        if (params.seriesName === '通过') {
          const w = weeks[idx]
          return w
            ? `${escapeHtml(w.weekStart)} 周 · 通过 ${w.solved} 题 · 活跃 ${w.activeDays} 天`
            : ''
        }
        if (params.seriesName === '提交') {
          const w = weeks[idx]
          return w ? `${escapeHtml(w.weekStart)} 周 · 提交 ${w.attempts} 次` : ''
        }
        // 活跃时段（hours）
        return `${idx} 时 · ${params.value ?? 0} 次提交`
      },
    },
    xAxis: [
      {
        type: 'category',
        gridIndex: 0,
        data: weeks.map((w) => weekLabel(w.weekStart)),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: palette.faint, fontSize: 10 },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: hourLabels,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: palette.faint, fontSize: 10 },
      },
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        minInterval: 1,
        splitLine: { lineStyle: { color: palette.border, type: 'dashed' } },
        axisLabel: { color: palette.faint, fontSize: 10 },
      },
      {
        type: 'value',
        gridIndex: 1,
        minInterval: 1,
        splitLine: { lineStyle: { color: palette.border, type: 'dashed' } },
        axisLabel: { color: palette.faint, fontSize: 10 },
      },
    ],
    series: [
      {
        name: '提交',
        type: 'bar',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: weeks.map((w) => w.attempts),
        barMaxWidth: 12,
        itemStyle: { color: palette.heatColors[3], borderRadius: [3, 3, 0, 0] },
      },
      {
        name: '通过',
        type: 'bar',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: weeks.map((w) => w.solved),
        barMaxWidth: 12,
        itemStyle: { color: palette.accent, borderRadius: [3, 3, 0, 0] },
      },
      {
        name: '活跃时段',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: hours,
        barMaxWidth: 10,
        itemStyle: { color: palette.heatColors[4], borderRadius: [3, 3, 0, 0] },
      },
    ],
  }
}

/* ---------- 薄弱点：按技能域分组 ---------- */

export interface WeakPointGroup {
  domainKey: string
  domainName: string
  items: WeakPoint[]
}

/** 按 domainKey 分组（保持 domainName 与输入首次出现顺序） */
export function buildWeakPointGroups(weakPoints: WeakPoint[]): WeakPointGroup[] {
  const groups = new Map<string, WeakPointGroup>()
  for (const w of weakPoints) {
    let group = groups.get(w.domainKey)
    if (!group) {
      group = { domainKey: w.domainKey, domainName: w.domainName, items: [] }
      groups.set(w.domainKey, group)
    }
    group.items.push(w)
  }
  return [...groups.values()]
}
