
/** SSR 回归测试：日历热力图必须能真正渲染出格子。
 * 曾经的 bug：heatmap 系列没有搭配 visualMap，ECharts 在开发模式下直接抛
 * "Heatmap must use with visualMap"，页面热力图整图空白。vitest 下
 * NODE_ENV 非 production，该检查生效，能守住这条回归。
 */

import { describe, expect, it } from 'vitest'
import { addDays } from '@/features/activity/model/dates'
import { echarts } from '@/features/activity/model/echarts-setup'
import { buildPalette } from '@/features/activity/model/echarts-theme'
import { buildHeatmapOption, weekCount } from '@/features/activity/model/heatmap-option'
import { generateDaily } from '@/features/activity/model/mock'
import type { DayActivity } from '@/features/activity/types'

const palette = buildPalette({
  hue: 160,
  dark: false,
  text: '#23211d',
  faint: '#a09a8e',
  surface: '#fdfdfc',
  surface2: '#efede8',
  border: '#e2dfd8',
})

describe('日历热力图 SSR 渲染', () => {
  it('setOption 不抛错且渲染出格子', () => {
    const daily = generateDaily('codeforces/demo_coder')
    const chart = echarts.init(null, null, {
      renderer: 'svg',
      ssr: true,
      width: 1400,
      height: 150,
    })
    try {
      expect(() => {
        chart.setOption(buildHeatmapOption(daily, null, palette))
      }).not.toThrow()
      const svg = chart.renderToSVGString()
      expect(svg).toContain('<svg')
      // SVG 渲染器下圆角格子画成 <path>：370 个数据格 + 370 个日历底格
      const pathCount = (svg.match(/<path /g) ?? []).length
      expect(pathCount).toBeGreaterThan(700)
      // 档位颜色内联在 fill 的 hsla() 串里，验证渲染结果真的带上了配色
      const fillCount = (svg.match(/fill="hsla?\(/g) ?? []).length
      expect(fillCount).toBeGreaterThan(100)
    } finally {
      chart.dispose()
    }
  })
})

describe('weekCount', () => {
  it('近一年的日序列占 53–55 列', () => {
    const weeks = weekCount(generateDaily('codeforces/demo_coder'))
    expect(weeks).toBeGreaterThanOrEqual(53)
    expect(weeks).toBeLessThanOrEqual(55)
  })

  it('首日为周日时前置空格计入列数', () => {
    // 2026-08-09 是周日，周一起始下首列有 6 个前置空格
    const daily: DayActivity[] = Array.from({ length: 7 }, (_, i) => ({
      date: addDays('2026-08-09', i),
      submissions: 0,
      solved: 0,
    }))
    expect(weekCount(daily)).toBe(2)
  })

  it('空序列返回 1', () => {
    expect(weekCount([])).toBe(1)
  })
})
