import { describe, expect, it } from 'vitest'
import { buildPalette, domainFill } from '@/features/activity/model/echarts-theme'

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

  it('颜色使用 zrender 可解析的逗号分隔 hsl/hsla 语法', () => {
    // zrender 颜色解析器只认旧式逗号语法；空格/斜杠的 CSS Color 4 写法
    // 会被解析为 undefined，导致 visualMap 等依赖颜色换算的场景拿不到颜色
    const p = buildPalette({ ...base, dark: false })
    const commaHsl = /^hsl\(\d+, \d+%, \d+%\)$/
    const commaHsla = /^hsla\(\d+, \d+%, \d+%, [\d.]+\)$/
    expect(p.accent).toMatch(commaHsl)
    for (const color of p.heatColors.slice(1)) {
      expect(color).toMatch(commaHsla)
    }
  })

  it('domainHues 生成 12 个不重复、随主题色相旋转的色相', () => {
    const p = buildPalette({ ...base, dark: false })
    expect(p.domainHues).toHaveLength(12)
    expect(new Set(p.domainHues).size).toBe(12)
    // 首个色相即主题色相本身
    expect(p.domainHues[0]).toBeCloseTo(160)
    // 换一个主题色相，整体等距旋转
    const p2 = buildPalette({ ...base, hue: 200, dark: false })
    expect(p2.domainHues[0]).toBeCloseTo(200)
    expect(p2.domainHues[1]).toBeCloseTo((200 + 30) % 360)
  })

  it('domainFill 明度随掌握度单调递增且遵循逗号 hsl 语法', () => {
    const commaHsl = /^hsl\(\d+, \d+%, \d+%\)$/
    const weak = domainFill(160, 0, false)
    const strong = domainFill(160, 1, false)
    expect(weak).toMatch(commaHsl)
    expect(strong).toMatch(commaHsl)
    // 掌握度 1 比 0 更亮、更饱和
    const lOf = (c: string) => Number(c.match(/(\d+)%\)$/)![1])
    expect(lOf(strong)).toBeGreaterThan(lOf(weak))
    // 明暗主题亮度不同
    expect(domainFill(160, 0.5, false)).not.toBe(domainFill(160, 0.5, true))
  })
})
