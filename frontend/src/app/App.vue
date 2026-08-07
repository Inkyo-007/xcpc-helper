<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  darkTheme,
  dateZhCN,
  lightTheme,
  NConfigProvider,
  NMessageProvider,
  zhCN,
} from 'naive-ui'
import AppShell from '@/app/AppShell.vue'
import { NAV_GROUPS } from '@/app/nav'
import { createThemeOverrides } from '@/app/theme'
import { useTheme } from '@/shared/composables/useTheme'

const { mode, hue, isDark, modeIcon, modeLabel, cycleMode, setMode, setHue } = useTheme()

const route = useRoute()
const router = useRouter()

const activePath = computed(() => route.path)
const openGroups = ref<Record<string, boolean>>({ templates: true })

const pageMeta = computed(() => ({
  group: route.meta.group ?? '',
  sub: route.meta.sub ?? '',
}))

const themeOverrides = computed(() => createThemeOverrides(!isDark.value, hue.value))

function navigate(path: string): void {
  void router.push(path)
}

function toggleGroup(id: string): void {
  const group = NAV_GROUPS.find((g) => g.id === id)
  if (!group) return
  openGroups.value[id] = !openGroups.value[id]
  if (
    openGroups.value[id] &&
    group.children &&
    !group.children.some((c) => c.to === activePath.value)
  ) {
    navigate(group.children[0].to)
  }
}

// 路由变化（含深链接进入）时自动展开所属分组
watch(
  activePath,
  (path) => {
    const group = NAV_GROUPS.find(
      (g) => g.to === path || g.children?.some((c) => c.to === path),
    )
    if (group) openGroups.value[group.id] = true
  },
  { immediate: true },
)

function onKeydown(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    if (activePath.value !== '/template/library') navigate('/template/library')
    requestAnimationFrame(() => {
      document.querySelector<HTMLInputElement>('.search-input input')?.focus()
    })
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <n-config-provider
    :theme="isDark ? darkTheme : lightTheme"
    :theme-overrides="themeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <n-message-provider placement="bottom">
      <AppShell
        :active-path="activePath"
        :open-groups="openGroups"
        :page-meta="pageMeta"
        :mode="mode"
        :mode-icon="modeIcon"
        :mode-label="modeLabel"
        :hue="hue"
        @navigate="navigate"
        @toggle="toggleGroup"
        @cycle-theme="cycleMode"
        @set-mode="setMode"
        @set-hue="setHue"
      >
        <router-view v-slot="{ Component }">
          <Transition name="page-swap" mode="out-in">
            <component :is="Component" />
          </Transition>
        </router-view>
      </AppShell>
    </n-message-provider>
  </n-config-provider>
</template>
