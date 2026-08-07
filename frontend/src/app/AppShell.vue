<script setup lang="ts">
import SideNav from '@/app/SideNav.vue'
import TopBar from '@/app/TopBar.vue'
import type { ThemeMode } from '@/shared/composables/useTheme'

defineProps<{
  activePath: string
  openGroups: Record<string, boolean>
  pageMeta: { group: string; sub: string }
  mode: ThemeMode
  modeIcon: 'sun' | 'moon' | 'monitor'
  modeLabel: string
  hue: number
}>()

const emit = defineEmits<{
  navigate: [path: string]
  toggle: [id: string]
  'cycle-theme': []
  'set-mode': [mode: ThemeMode]
  'set-hue': [value: number]
}>()
</script>

<template>
  <div class="app-shell">
    <SideNav
      :active-path="activePath"
      :open-groups="openGroups"
      @navigate="(path) => emit('navigate', path)"
      @toggle="(id) => emit('toggle', id)"
    />
    <main class="main-pane">
      <TopBar
        :page-meta="pageMeta"
        :mode="mode"
        :mode-icon="modeIcon"
        :mode-label="modeLabel"
        :hue="hue"
        @cycle-theme="emit('cycle-theme')"
        @set-mode="(value) => emit('set-mode', value)"
        @set-hue="(value) => emit('set-hue', value)"
      />
      <section class="page-stage">
        <slot />
      </section>
    </main>
  </div>
</template>
