<script setup lang="ts">
import { Code2, ChevronRight, LayoutTemplate, Settings, Timer } from 'lucide-vue-next'
import { NAV_GROUPS } from '@/app/nav'
import type { NavGroup } from '@/app/nav'

const props = defineProps<{
  activePath: string
  openGroups: Record<string, boolean>
}>()

const emit = defineEmits<{
  navigate: [path: string]
  toggle: [id: string]
}>()

const iconMap = {
  template: LayoutTemplate,
  timer: Timer,
  settings: Settings,
}

function isGroupActive(group: NavGroup): boolean {
  if (group.to === props.activePath) return true
  return group.children?.some((child) => child.to === props.activePath) ?? false
}

function onGroupClick(group: NavGroup): void {
  if (group.children) emit('toggle', group.id)
  else if (group.to) emit('navigate', group.to)
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-mark"><Code2 :size="17" :stroke-width="2.5" /></span>
      <span class="brand-name">XCPC Helper</span>
      <span class="brand-ver">v0.2</span>
    </div>
    <nav class="nav-scroll" aria-label="功能导航">
      <div
        v-for="group in NAV_GROUPS"
        :key="group.id"
        class="nav-group"
        :class="{ open: openGroups[group.id] }"
      >
        <button
          type="button"
          class="nav-item"
          :class="{ active: isGroupActive(group) }"
          @click="onGroupClick(group)"
        >
          <component :is="iconMap[group.icon]" :size="17" />
          <span class="nav-label">{{ group.label }}</span>
          <span v-if="group.badge" class="nav-badge">{{ group.badge }}</span>
          <ChevronRight v-if="group.children" class="nav-chev" :size="14" />
        </button>
        <div v-if="group.children" class="nav-sub">
          <button
            v-for="child in group.children"
            :key="child.id"
            type="button"
            class="nav-sub-item"
            :class="{ active: activePath === child.to }"
            @click="emit('navigate', child.to)"
          >
            <span class="sub-dot"></span>
            <span>{{ child.label }}</span>
          </button>
        </div>
      </div>
    </nav>
    <div class="sidebar-foot">
      <span class="status-dot" aria-hidden="true"></span>
      <span>本地模式 · 数据保存在本机</span>
    </div>
  </aside>
</template>
