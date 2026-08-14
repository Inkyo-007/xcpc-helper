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
  /** 是否暗色主题（供节点按掌握度调明度等派生色使用） */
  dark: boolean
  /** 6 档热力色（档位定义见 model/heatmap.ts），0 档为空格色 */
  heatColors: string[]
  tooltipBg: string
  tooltipText: string
  /** 12 个技能域分类色相（deg），随主题 --hue 整体旋转；节点/图例据此填色 */
  domainHues: number[]
}

/** AC 档位的透明度梯度（档 1 为"有提交无 AC"的最低档） */
const HEAT_ALPHAS = [0.16, 0.42, 0.62, 0.82, 1]

/** 技能域分类色相数量：与后端 DOMAIN_ORDER 的 12 个固定域对齐（other 兜底复用首色） */
export const DOMAIN_HUE_COUNT = 12
const DOMAIN_HUE_STEP = 360 / DOMAIN_HUE_COUNT

/** 以主题色相为起点、360° 均布的 12 个分类色相（各域视觉可区分，且随 --hue 联动） */
export function domainHues(hue: number): number[] {
  return Array.from({ length: DOMAIN_HUE_COUNT }, (_, i) => (hue + i * DOMAIN_HUE_STEP) % 360)
}

/**
 * 技能树节点填色：域色相 + 掌握度驱动的明度/饱和度。
 * 掌握度越高越鲜艳明亮（强技能"弹出"、弱技能"隐退"），且保持所属域的色相身份。
 */
export function domainFill(hue: number, proficiency: number, dark: boolean): string {
  const p = Math.min(1, Math.max(0, proficiency))
  const saturation = 52 + 18 * p
  const baseLight = dark ? 62 : 46
  const lightness = baseLight * (0.6 + 0.4 * p)
  // zrender 只认逗号分隔的旧式 hsl() 语法（见 buildPalette 注释）
  return `hsl(${Math.round(hue)}, ${Math.round(saturation)}%, ${Math.round(lightness)}%)`
}

export function buildPalette(vars: ChartThemeVars): ChartPalette {
  const lightness = vars.dark ? 62 : 48
  // 注意必须用逗号分隔的旧式 hsla() 语法：zrender 的颜色解析器不支持
  // CSS Color 4 的空格/斜杠语法，解析失败会导致依赖颜色换算的场景（如 visualMap）拿不到颜色
  const heat = (alpha: number) => `hsla(${vars.hue}, 68%, ${lightness}%, ${alpha})`
  return {
    accent: `hsl(${vars.hue}, 68%, ${vars.dark ? 55 : 48}%)`,
    text: vars.text,
    faint: vars.faint,
    surface: vars.surface,
    border: vars.border,
    dark: vars.dark,
    heatColors: [vars.surface2, ...HEAT_ALPHAS.map(heat)],
    // Tooltip 与全局主题一致：背景取文字色、文字取底色，明暗下均可读
    tooltipBg: vars.text,
    tooltipText: vars.dark ? '#191816' : '#f6f5f2',
    domainHues: domainHues(vars.hue),
  }
}
