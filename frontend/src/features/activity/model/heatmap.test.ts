import { describe, expect, it } from 'vitest'
import { heatLevel } from '@/features/activity/model/heatmap'

describe('heatLevel', () => {
  it('无提交为 0 档', () => {
    expect(heatLevel(0, 0)).toBe(0)
  })

  it('有提交无 AC 为最低档', () => {
    expect(heatLevel(1, 0)).toBe(1)
    expect(heatLevel(12, 0)).toBe(1)
  })

  it('按 AC 数分桶', () => {
    expect(heatLevel(1, 1)).toBe(2)
    expect(heatLevel(3, 2)).toBe(3)
    expect(heatLevel(4, 3)).toBe(3)
    expect(heatLevel(6, 4)).toBe(4)
    expect(heatLevel(8, 5)).toBe(4)
    expect(heatLevel(10, 6)).toBe(5)
    expect(heatLevel(14, 10)).toBe(5)
    expect(heatLevel(30, 25)).toBe(5)
  })
})
