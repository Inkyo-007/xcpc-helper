import { describe, expect, it } from 'vitest'
import { monthlySolved, weeklySolved } from '@/features/activity/model/bars'
import type { DayActivity } from '@/features/activity/types'

function day(date: string, solved: number): DayActivity {
  return { date, submissions: solved + 1, solved }
}

describe('weeklySolved', () => {
  it('取序列末尾 7 天并给出星期标签', () => {
    const daily = [
      day('2026-08-05', 1),
      day('2026-08-06', 2),
      day('2026-08-07', 3),
      day('2026-08-08', 4),
      day('2026-08-09', 5),
      day('2026-08-10', 6),
      day('2026-08-11', 7),
      day('2026-08-12', 8),
    ]
    const bars = weeklySolved(daily)
    expect(bars).toHaveLength(7)
    expect(bars[0].key).toBe('2026-08-06')
    expect(bars[6].value).toBe(8)
    // 2026-08-12 是周三
    expect(bars[6].label).toBe('周三')
  })
})

describe('monthlySolved', () => {
  it('按月份聚合并保留最近 12 个月', () => {
    const daily: DayActivity[] = []
    for (let m = 1; m <= 14; m++) {
      const key = `2025-${String(m).padStart(2, '0')}-15`
      daily.push(day(key, m))
    }
    const bars = monthlySolved(daily)
    expect(bars).toHaveLength(12)
    expect(bars[0].key).toBe('2025-03')
    expect(bars[0].label).toBe('3月')
    expect(bars[11].value).toBe(14)
  })
})
