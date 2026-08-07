/** Naive UI 全局主题定制：由明/暗标志与主题色相生成 themeOverrides。 */

import type { GlobalThemeOverrides } from 'naive-ui'

export function createThemeOverrides(light: boolean, hue: number): GlobalThemeOverrides {
  const accent = `hsl(${hue}, 68%, ${light ? 48 : 24}%)`
  const accentHover = `hsl(${hue}, 72%, ${light ? 36 : 32}%)`
  const accentPressed = `hsl(${hue}, 70%, ${light ? 40 : 28}%)`
  const accentSoft = `hsla(${hue}, 60%, 40%, 0.16)`

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
    },
    Message: {
      color: 'var(--text)',
      textColor: 'var(--bg)',
      borderRadius: '6px',
    },
  }
}
