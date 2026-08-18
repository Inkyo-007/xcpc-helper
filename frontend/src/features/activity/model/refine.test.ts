import { describe, expect, it } from 'vitest'
import { estimateRefineDuration } from '@/features/activity/model/refine'

describe('estimateRefineDuration', () => {
  it('零存量无需精化', () => {
    expect(estimateRefineDuration(0)).toBe('无需精化')
  })

  it('分钟量级向上取整', () => {
    expect(estimateRefineDuration(1)).toBe('约 1 分钟')
    expect(estimateRefineDuration(13)).toBe('约 2 分钟') // 13×5s=65s → 2 分钟
    expect(estimateRefineDuration(700)).toBe('约 59 分钟')
  })

  it('小时量级保留一位小数', () => {
    expect(estimateRefineDuration(720)).toBe('约 1 小时') // 720×5s=60min
    expect(estimateRefineDuration(2000)).toBe('约 2.8 小时')
  })
})
