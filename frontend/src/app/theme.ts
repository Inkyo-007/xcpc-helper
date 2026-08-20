/** Naive UI 全局主题定制：由明/暗标志与主题色相生成 themeOverrides。 */

import type { GlobalThemeOverrides } from 'naive-ui'

/** 根据色相计算饱和度衰减系数：暖色区（红/粉/橙）饱和度过高时刺眼，
 *  需按色相偏移量衰减。冷色区（青/蓝/绿）保持原饱和度。
 *  衰减曲线为平滑余弦，在 peakHue 处衰减最大，offset 处无衰减。 */
export function saturationDampen(hue: number, baseS: number, peakHue: number, maxDampen: number): number {
  const diff = Math.abs(hue - peakHue)
  const dist = Math.min(diff, 360 - diff)
  const range = 60 // 衰减影响范围 ±60°
  if (dist >= range) return baseS
  const factor = (1 + Math.cos((dist / range) * Math.PI)) / 2 // 1→0 平滑过渡
  return Math.round(baseS - maxDampen * factor)
}

export function createThemeOverrides(light: boolean, hue: number): GlobalThemeOverrides {
  // 亮色模式：暖色区（330°±60° 即粉/玫红）饱和度衰减 18%，避免刺眼
  const lightS = saturationDampen(hue, 68, 330, 18)
  // 暗色模式：整体饱和度降低 10%，明度降低至 42%，更柔和不扎眼
  const darkS = saturationDampen(hue, 68, 330, 12) - 10
  const s = light ? lightS : Math.max(50, darkS)
  const l = light ? 48 : 42

  const accent = `hsl(${hue}, ${s}%, ${l}%)`
  const accentHover = `hsl(${hue}, ${Math.min(100, s + 4)}%, ${light ? 36 : 34}%)`
  const accentPressed = `hsl(${hue}, ${Math.min(100, s + 2)}%, ${light ? 40 : 38}%)`
  const accentSoft = `hsla(${hue}, ${Math.min(100, s - 8)}%, ${light ? 40 : 42}%, ${light ? 0.16 : 0.18})`

  return {
    common: {
      primaryColor: accent,
      primaryColorHover: accentHover,
      primaryColorPressed: accentPressed,
      primaryColorSuppl: accentHover,
      borderRadius: '8px',
      borderRadiusSmall: '6px',
      fontFamily: 'var(--font-ui)',
      fontFamilyMono: 'var(--font-mono)',
      textColorBase: 'var(--text)',
      bodyColor: 'var(--bg)',
    },
    Button: {
      textColorPrimary: 'var(--on-accent)',
      colorPrimary: accent,
      colorHoverPrimary: accentHover,
      colorPressedPrimary: accentPressed,
      colorFocusPrimary: accentHover,
      borderPrimary: `1px solid ${accent}`,
      borderHoverPrimary: `1px solid ${accentHover}`,
      borderPressedPrimary: `1px solid ${accentPressed}`,
      borderRadiusMedium: '6px',
      borderRadiusSmall: '6px',
    },
    Input: {
      color: 'var(--surface)',
      colorFocus: 'var(--surface)',
      border: '1px solid var(--border)',
      borderHover: '1px solid var(--border-strong)',
      borderFocus: '1px solid var(--accent)',
      boxShadowFocus: `0 0 0 3px ${accentSoft}`,
      textColor: 'var(--text)',
      placeholderColor: 'var(--faint)',
      caretColor: 'var(--accent)',
    },
    Select: {
      color: 'var(--surface)',
      colorHover: 'var(--surface)',
      colorActive: 'var(--surface)',
      border: '1px solid var(--border)',
      borderHover: '1px solid var(--border-strong)',
      borderFocus: '1px solid var(--accent)',
      boxShadowFocus: `0 0 0 3px ${accentSoft}`,
      textColor: 'var(--text)',
      placeholderColor: 'var(--faint)',
    },
    Modal: {
      color: 'var(--surface)',
      borderRadius: '12px',
    },
    Popover: {
      color: 'var(--surface)',
      borderRadius: '8px',
      boxShadow: 'var(--shadow-pop)',
      border: '1px solid var(--border)',
    },
    Slider: {
      fillColor: accent,
      fillColorHover: accent,
      railColor: 'var(--border)',
      railColorHover: 'var(--border-strong)',
      handleColor: '#ffffff',
      handleBoxShadow: '0 1px 4px rgb(0 0 0 / 0.35)',
    },
    Tooltip: {
      color: 'var(--text)',
      textColor: 'var(--bg)',
      borderRadius: '6px',
      // NTooltip 内部复用 NPopover 渲染：背景色取自 Popover 主题而非 Tooltip.color，
      // 必须同步覆盖 peers.Popover，否则背景会沿用全局 Popover 的 var(--surface)，
      // 与文字色 var(--bg) 撞色（明暗主题下文字均不可读）
      peers: {
        Popover: {
          color: 'var(--text)',
          textColor: 'var(--bg)',
          borderRadius: '6px',
        },
      },
    },
    Message: {
      color: 'var(--text)',
      textColor: 'var(--bg)',
      borderRadius: '6px',
    },
  }
}
