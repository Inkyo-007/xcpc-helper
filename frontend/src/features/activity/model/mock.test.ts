/** generateEntries 回归测试：爆发日提交数可超过题库容量。
 * 曾经的 bug——pick() 死等一个没用过的题目下标，提交数 > 题库量时
 * while 永不终止，点击热力图格子后整页卡死。若回归，本测试会因
 * vitest 超时（默认 5s）失败，而不是无限挂起。
 */

import { describe, expect, it } from 'vitest'
import { generateEntries, PLATFORMS } from '@/features/activity/model/mock'
import type { DayActivity } from '@/features/activity/types'

describe('generateEntries', () => {
  it('提交数超过题库量时仍正常生成且统计一致', () => {
    for (const platform of PLATFORMS) {
      const day: DayActivity = { date: '2026-08-10', submissions: 20, solved: 7 }
      const entries = generateEntries(platform.id, 'demo_coder', day)
      expect(entries.length).toBe(day.submissions)
      expect(entries.filter((e) => e.verdict === 'AC').length).toBe(day.solved)
      expect(new Set(entries.map((e) => e.id)).size).toBe(day.submissions)
    }
  })

  it('生成结果按时间升序且确定性可复现', () => {
    const day: DayActivity = { date: '2026-08-11', submissions: 5, solved: 3 }
    const a = generateEntries('luogu', 'demo_coder', day)
    const b = generateEntries('luogu', 'demo_coder', day)
    expect(a).toEqual(b)
    const times = a.map((e) => e.time)
    expect([...times].sort()).toEqual(times)
  })
})
