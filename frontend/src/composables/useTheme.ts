import { computed, ref, watchEffect } from 'vue'
import { load, save } from '@/utils/storage'

export type ThemeMode = 'light' | 'dark' | 'system'

const THEME_KEY = 'xc-theme-mode'
const HUE_KEY = 'xc-hue'
const ORDER: ThemeMode[] = ['light', 'dark', 'system']

const MODE_LABELS: Record<ThemeMode, string> = {
  light: '亮色',
  dark: '暗色',
  system: '跟随系统',
}

const media = window.matchMedia('(prefers-color-scheme: dark)')

export function useTheme() {
  const mode = ref<ThemeMode>(load<ThemeMode>(THEME_KEY, 'system'))
  const hue = ref<number>(load<number>(HUE_KEY, 160))

  const isDark = ref(mode.value === 'dark' || (mode.value === 'system' && media.matches))
  const modeLabel = computed(() => MODE_LABELS[mode.value])
  const modeIcon = computed(() => (mode.value === 'light' ? 'sun' : mode.value === 'dark' ? 'moon' : 'monitor'))

  function refreshDark(): void {
    isDark.value = mode.value === 'dark' || (mode.value === 'system' && media.matches)
  }

  watchEffect(() => {
    refreshDark()
    document.documentElement.dataset.theme = isDark.value ? 'dark' : 'light'
    document.documentElement.style.setProperty('--hue', String(hue.value))
    save(THEME_KEY, mode.value)
    save(HUE_KEY, hue.value)
  })

  function cycleMode(): void {
    const index = ORDER.indexOf(mode.value)
    mode.value = ORDER[(index + 1) % ORDER.length]
  }

  function setMode(value: ThemeMode): void {
    mode.value = value
  }

  function setHue(value: number): void {
    hue.value = Math.round(Math.min(360, Math.max(0, value)))
  }

  media.addEventListener('change', () => {
    if (mode.value === 'system') refreshDark()
  })

  return {
    mode,
    hue,
    isDark,
    modeLabel,
    modeIcon,
    cycleMode,
    setMode,
    setHue,
  }
}
