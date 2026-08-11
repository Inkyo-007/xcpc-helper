/** 通过数柱状图数据派生（纯函数）：从日序列派生近 7 天 / 近 12 个月 AC 数。 */

import type { DayActivity } from '@/features/activity/types'
import { monthKey, parseDate, weekdayCn } from '@/features/activity/model/dates'

export interface BarDatum {
  /** 稳定标识（日期或月份） */
  key: string
  /** 轴标签 */
  label: string
  value: number
  /** tooltip 用的完整描述 */
  hint: string
}

/** 近 7 天（含今天）AC 数；日序列按日期升序、末尾为今天。 */
export function weeklySolved(daily: DayActivity[]): BarDatum[] {
  return daily.slice(-7).map((d) => ({
    key: d.date,
    label: `周${weekdayCn(d.date)}`,
    value: d.solved,
    hint: d.date,
  }))
}

/** 近 12 个月（含本月）AC 数。 */
export function monthlySolved(daily: DayActivity[]): BarDatum[] {
  const byMonth = new Map<string, number>()
  for (const d of daily) {
    const key = monthKey(d.date)
    byMonth.set(key, (byMonth.get(key) ?? 0) + d.solved)
  }
  return [...byMonth.entries()].slice(-12).map(([key, value]) => {
    const month = parseDate(`${key}-01`).getMonth() + 1
    return { key, label: `${month}月`, value, hint: key }
  })
}
