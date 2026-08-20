/** ECharts 主题桥接（纯函数）：把主题变量换算为图表配色。
 * DOM 读取（getComputedStyle / MutationObserver）在组件层完成，这里只负责纯换算。
 */

import { saturationDampen } from '@/app/theme'

export interface ChartThemeVars {
  hue: number
  dark: boolean
  text: string
  faint: string
  surface: string
  surface2: string
  border: string
}

export interface ChartPalette {
  accent: string
  text: string
  faint: string
  surface: string
  border: string
  /** 6 档热力色（档位定义见 model/heatmap.ts），0 档为空格色 */
  heatColors: string[]
  tooltipBg: string
  tooltipText: string
}

/** AC 档位的透明度梯度（档 1 为"有提交无 AC"的最低档） */
const HEAT_ALPHAS = [0.16, 0.42, 0.62, 0.82, 1]

export function buildPalette(vars: ChartThemeVars): ChartPalette {
  const light = !vars.dark
  const lightS = saturationDampen(vars.hue, 68, 330, 18)
  const darkS = saturationDampen(vars.hue, 68, 330, 12) - 10
  const s = light ? lightS : Math.max(50, darkS)
  const l = light ? 48 : 42

  // 注意必须用逗号分隔的旧式 hsla() 语法：zrender 的颜色解析器不支持
  // CSS Color 4 的空格/斜杠语法，解析失败会导致依赖颜色换算的场景（如 visualMap）拿不到颜色
  const heat = (alpha: number) => `hsla(${vars.hue}, ${s}%, ${l}%, ${alpha})`
  return {
    accent: `hsl(${vars.hue}, ${s}%, ${light ? 48 : 55}%)`,
    text: vars.text,
    faint: vars.faint,
    surface: vars.surface,
    border: vars.border,
    heatColors: [vars.surface2, ...HEAT_ALPHAS.map(heat)],
    // Tooltip 与全局主题一致：背景取文字色、文字取底色，明暗下均可读
    tooltipBg: vars.text,
    tooltipText: vars.dark ? '#191816' : '#f6f5f2',
  }
}
