/** ECharts 主题桥接（纯函数）：把主题变量换算为图表配色。
 * DOM 读取（getComputedStyle / MutationObserver）在组件层完成，这里只负责纯换算。
 */

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
  const lightness = vars.dark ? 62 : 48
  const heat = (alpha: number) => `hsl(${vars.hue} 68% ${lightness}% / ${alpha})`
  return {
    accent: `hsl(${vars.hue} 68% ${vars.dark ? 55 : 48}%)`,
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
