import { describe, expect, it } from 'vitest'
import { buildPalette } from '@/features/activity/model/echarts-theme'

const base = {
  hue: 160,
  text: '#23211d',
  faint: '#a09a8e',
  surface: '#fdfdfc',
  surface2: '#efede8',
  border: '#e2dfd8',
}

describe('buildPalette', () => {
  it('生成 6 档热力色，0 档为空格色', () => {
    const p = buildPalette({ ...base, dark: false })
    expect(p.heatColors).toHaveLength(6)
    expect(p.heatColors[0]).toBe(base.surface2)
    expect(p.heatColors[5]).toContain('160')
  })

  it('明暗主题使用不同亮度', () => {
    const light = buildPalette({ ...base, dark: false })
    const dark = buildPalette({ ...base, dark: true })
    expect(light.heatColors[3]).not.toBe(dark.heatColors[3])
    expect(light.accent).toContain('48%')
    expect(dark.accent).toContain('55%')
  })
})
