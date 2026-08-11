
/** SSR 回归测试：日历热力图必须能真正渲染出格子。
 * 曾经的 bug：heatmap 系列没有搭配 visualMap，ECharts 在开发模式下直接抛
 * "Heatmap must use with visualMap"，页面热力图整图空白。vitest 下
 * NODE_ENV 非 production，该检查生效，能守住这条回归。
 */

import { describe, expect, it } from 'vitest'
import { echarts } from '@/features/activity/model/echarts-setup'
import { buildPalette } from '@/features/activity/model/echarts-theme'
import { buildHeatmapOption } from '@/features/activity/model/heatmap-option'
import { generateDaily } from '@/features/activity/model/mock'

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
