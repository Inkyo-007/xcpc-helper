/** 热力图 DOM 网格的纯函数层：日序列展开为列优先（列 = 周）的格子数组，
 * 并推导月份标签位置。网格固定周日起始（行 0 = 周日），与原 ECharts
 * calendar 的内部定位一致；档位着色规则见 model/heatmap.ts（§4.3）。
 */

import { parseDate } from '@/features/activity/model/dates'
import { heatLevel, type HeatLevel } from '@/features/activity/model/heatmap'
import type { DayActivity } from '@/features/activity/types'

const DAY_MS = 86400000

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

/** 一个日期格子；范围外的占位格为 null */
export interface HeatCell {
  date: string
  submissions: number
  solved: number
  level: HeatLevel
}

/** 日序列占用的列（周）数：前置空格（首周周日之前的空位）计入首列 */
export function weekCount(daily: DayActivity[]): number {
  if (daily.length === 0) return 1
  const first = parseDate(daily[0].date)
  const last = parseDate(daily[daily.length - 1].date)
  const days = Math.round((last.getTime() - first.getTime()) / DAY_MS) + 1
  const leadBlanks = first.getDay()
  return Math.max(1, Math.ceil((days + leadBlanks) / 7))
}

/** 日序列 → 列优先格子数组（长度恰为 weekCount × 7；范围外占位为 null） */
export function buildHeatmapCells(daily: DayActivity[]): (HeatCell | null)[] {
  if (daily.length === 0) return []
  const lead = parseDate(daily[0].date).getDay()
  const cells: (HeatCell | null)[] = Array.from({ length: lead }, () => null)
  for (const d of daily) {
    cells.push({
      date: d.date,
      submissions: d.submissions,
      solved: d.solved,
      level: heatLevel(d.submissions, d.solved),
    })
  }
  const weeks = Math.ceil(cells.length / 7)
  while (cells.length < weeks * 7) cells.push(null)
  return cells
}

/** 月份标签：每月 1 日所在列标注月份；起始月份的 1 日不在范围内时补在首列 */
export function buildMonthLabels(cells: (HeatCell | null)[]): { week: number; label: string }[] {
  const labels: { week: number; label: string }[] = []
  for (let i = 0; i < cells.length; i++) {
    const cell = cells[i]
    if (!cell || !cell.date.endsWith('-01')) continue
    labels.push({ week: Math.floor(i / 7), label: MONTH_LABELS[parseDate(cell.date).getMonth()] })
  }
  if (cells.length > 0 && labels[0]?.week !== 0) {
    const first = cells.find((c) => c !== null)
    if (first) labels.unshift({ week: 0, label: MONTH_LABELS[parseDate(first.date).getMonth()] })
  }
  return labels
}
