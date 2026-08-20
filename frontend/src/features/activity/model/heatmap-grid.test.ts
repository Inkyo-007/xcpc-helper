/** 热力图 DOM 网格纯函数测试：列数推算、格子展开（前置/末尾占位）、月份标签。 */

import { describe, expect, it } from 'vitest'
import { addDays } from '@/features/activity/model/dates'
import {
  buildHeatmapCells,
  buildMonthLabels,
  weekCount,
} from '@/features/activity/model/heatmap-grid'
import type { DayActivity } from '@/features/activity/types'

function makeDaily(start: string, days: number): DayActivity[] {
  return Array.from({ length: days }, (_, i) => ({
    date: addDays(start, i),
    submissions: 0,
    solved: 0,
  }))
}

describe('weekCount', () => {
  it('近一年的日序列占 53–55 列', () => {
    // 370 天连续序列（首日 2025-08-10 为周日，无前置占位）
    const weeks = weekCount(makeDaily('2025-08-10', 370))
    expect(weeks).toBeGreaterThanOrEqual(53)
    expect(weeks).toBeLessThanOrEqual(55)
  })

  it('首日为周日时恰好占一列', () => {
    // 2026-08-09 是周日，周日起始网格下连续 7 天正好一列
    expect(weekCount(makeDaily('2026-08-09', 7))).toBe(1)
  })

  it('首日为周一时前置空格计入列数', () => {
    // 2026-08-10 是周一，周日起始网格下首列有 1 个前置空格
    expect(weekCount(makeDaily('2026-08-10', 7))).toBe(2)
  })

  it('空序列返回 1', () => {
    expect(weekCount([])).toBe(1)
  })
})

describe('buildHeatmapCells', () => {
  it('空序列返回空数组', () => {
    expect(buildHeatmapCells([])).toEqual([])
  })

  it('首日为周日时无前置占位', () => {
    const cells = buildHeatmapCells(makeDaily('2026-08-09', 7))
    expect(cells).toHaveLength(7)
    expect(cells[0]?.date).toBe('2026-08-09')
  })

  it('首日非周日时前置 null 占位，末尾不足一周补 null', () => {
    // 2026-08-10 周一 → 前置 1 格；7 天 + 1 占位 = 8，补齐到 14
    const cells = buildHeatmapCells(makeDaily('2026-08-10', 7))
    expect(cells).toHaveLength(14)
    expect(cells[0]).toBeNull()
    expect(cells[1]?.date).toBe('2026-08-10')
    expect(cells[7]?.date).toBe('2026-08-16')
    expect(cells.slice(8).every((c) => c === null)).toBe(true)
  })

  it('格子带有着色档位', () => {
    const cells = buildHeatmapCells([
      { date: '2026-08-09', submissions: 0, solved: 0 },
      { date: '2026-08-10', submissions: 5, solved: 0 },
      { date: '2026-08-11', submissions: 5, solved: 4 },
    ])
    expect(cells[0]?.level).toBe(0)
    expect(cells[1]?.level).toBe(1)
    expect(cells[2]?.level).toBe(4)
  })

  it('近一年序列格子数 = 周数 × 7', () => {
    const daily = makeDaily('2025-08-10', 370)
    expect(buildHeatmapCells(daily)).toHaveLength(weekCount(daily) * 7)
  })
})

describe('buildMonthLabels', () => {
  it('每月 1 日所在列出标签', () => {
    // 2026-07-20 起 40 天，覆盖 2026-08-01
    const cells = buildHeatmapCells(makeDaily('2026-07-20', 40))
    const labels = buildMonthLabels(cells)
    const aug = labels.find((l) => l.label === '8月')
    expect(aug).toBeDefined()
    // 2026-08-01 是序列第 12 天（下标 12），2026-07-20 是周一 → 前置 1 格，下标 13，第 1 列
    expect(aug?.week).toBe(Math.floor((1 + 12) / 7))
  })

  it('起始月份的 1 日不在范围内时首列补标签', () => {
    // 2026-07-20 起 10 天：范围内没有任何 1 日
    const cells = buildHeatmapCells(makeDaily('2026-07-20', 10))
    const labels = buildMonthLabels(cells)
    expect(labels).toEqual([{ week: 0, label: '7月' }])
  })

  it('首列已含 1 日标签时不重复补', () => {
    // 2026-08-01 是周六 → 前置 6 格，1 日落在首列（下标 6，week 0）
    const cells = buildHeatmapCells(makeDaily('2026-08-01', 14))
    const labels = buildMonthLabels(cells)
    expect(labels[0]).toEqual({ week: 0, label: '8月' })
    expect(labels.filter((l) => l.label === '8月')).toHaveLength(1)
  })
})
