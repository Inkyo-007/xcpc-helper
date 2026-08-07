<script setup lang="ts">
import { ref } from 'vue'
import { Check, Monitor, Moon, Palette, Sun } from 'lucide-vue-next'
import { NPopover, NSlider, NTooltip } from 'naive-ui'
import type { ThemeMode } from '@/shared/composables/useTheme'

defineProps<{
  pageMeta: { group: string; sub: string }
  mode: ThemeMode
  modeIcon: 'sun' | 'moon' | 'monitor'
  modeLabel: string
  hue: number
}>()

const emit = defineEmits<{
  'cycle-theme': []
  'set-mode': [mode: ThemeMode]
  'set-hue': [value: number]
}>()

const hueOpen = ref(false)
const themeMenuOpen = ref(false)
const PRESETS = [12, 25, 45, 90, 160, 200, 260, 320]
const iconMap = {
  sun: Sun,
  moon: Moon,
  monitor: Monitor,
}
const THEME_OPTIONS = [
  { value: 'light' as ThemeMode, label: '亮色', icon: Sun },
  { value: 'dark' as ThemeMode, label: '暗色', icon: Moon },
  { value: 'system' as ThemeMode, label: '跟随系统', icon: Monitor },
]

function setHue(value: number): void {
  emit('set-hue', value)
}

function chooseTheme(value: ThemeMode): void {
  emit('set-mode', value)
  themeMenuOpen.value = false
}
</script>

<template>
  <header class="topbar">
    <div class="crumb">
      <h1 class="page-title">{{ pageMeta.group }}</h1>
      <span class="page-sub">{{ pageMeta.sub ? `/ ${pageMeta.sub}` : '' }}</span>
    </div>
    <div class="top-actions">
      <n-popover
        :show="hueOpen"
        :offset="10"
        placement="bottom-end"
        trigger="hover"
        @update:show="hueOpen = $event"
      >
        <template #trigger>
          <button type="button" class="icon-btn" aria-label="调整主题色相">
            <Palette :size="17" />
          </button>
        </template>
        <div class="hue-pop">
          <div class="hue-pop-head">
            <span>主题色相</span>
            <span class="hue-value">{{ hue }}°</span>
          </div>
          <n-slider
            :value="hue"
            :min="0"
            :max="360"
            :step="1"
            @update:value="setHue"
          />
          <div class="hue-presets">
            <n-tooltip v-for="h in PRESETS" :key="h">
              <template #trigger>
                <button
                  type="button"
                  class="swatch"
                  :class="{ active: h === hue }"
                  :style="{ background: `hsl(${h} 60% 50%)` }"
                  @click="setHue(h)"
                ></button>
              </template>
              色相 {{ h }}°
            </n-tooltip>
          </div>
        </div>
      </n-popover>
      <n-popover
        :show="themeMenuOpen"
        :offset="10"
        placement="bottom-end"
        trigger="hover"
        content-style="padding: 4px"
        @update:show="themeMenuOpen = $event"
      >
        <template #trigger>
          <button
            type="button"
            class="icon-btn theme-btn"
            :aria-label="`切换主题，当前 ${modeLabel}`"
            @click="emit('cycle-theme')"
          >
            <component :is="iconMap[modeIcon]" :size="17" />
          </button>
        </template>
        <div class="theme-menu">
          <button
            v-for="option in THEME_OPTIONS"
            :key="option.value"
            type="button"
            class="theme-option"
            :class="{ active: mode === option.value }"
            @click="chooseTheme(option.value)"
          >
            <component :is="option.icon" :size="15" />
            <span>{{ option.label }}</span>
            <Check v-if="mode === option.value" :size="14" class="theme-check" />
          </button>
        </div>
      </n-popover>
    </div>
  </header>
</template>
