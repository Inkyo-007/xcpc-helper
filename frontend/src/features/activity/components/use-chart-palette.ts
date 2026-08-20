/** 图表主题桥接的 DOM 侧：监听 documentElement 的主题属性变化，
 * 实时把 CSS 变量换算为 ECharts 配色（换算逻辑在 model/echarts-theme.ts）。
 */

import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  buildPalette,
  type ChartPalette,
  type ChartThemeVars,
} from '@/features/activity/model/echarts-theme'

function readVars(): ChartThemeVars {
  const el = document.documentElement
  const cs = getComputedStyle(el)
  const hueRaw = cs.getPropertyValue('--hue').trim()
  return {
    hue: hueRaw === '' ? 160 : Number(hueRaw),
    dark: el.dataset.theme === 'dark',
    text: cs.getPropertyValue('--text').trim(),
    faint: cs.getPropertyValue('--faint').trim(),
    surface: cs.getPropertyValue('--surface').trim(),
    surface2: cs.getPropertyValue('--surface-2').trim(),
    border: cs.getPropertyValue('--border').trim(),
  }
}

export function useChartPalette() {
  const palette = ref<ChartPalette>(buildPalette(readVars()))
  let observer: MutationObserver | null = null

  const refresh = (): void => {
    palette.value = buildPalette(readVars())
  }

  onMounted(() => {
    refresh()
    observer = new MutationObserver(refresh)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'style'],
    })
  })

  onBeforeUnmount(() => observer?.disconnect())

  return palette
}
