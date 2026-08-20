import { describe, expect, it } from 'vitest'
import { recentDateStr } from '@/features/activity/model/dates'

describe('recentDateStr', () => {
  const today = '2026-08-13'

  it('当年的日期省略年份（MM-DD）', () => {
    expect(recentDateStr('2026-01-02', today)).toBe('01-02')
    expect(recentDateStr('2026-12-31', today)).toBe('12-31')
    expect(recentDateStr('2026-08-13', today)).toBe('08-13')
  })

  it('往年的日期显示完整 YYYY-MM-DD', () => {
    expect(recentDateStr('2025-08-13', today)).toBe('2025-08-13')
    expect(recentDateStr('2027-01-01', today)).toBe('2027-01-01')
  })

  it('默认以今天为基准', () => {
    const label = recentDateStr('2000-01-01')
    expect(label).toBe('2000-01-01')
  })
})
