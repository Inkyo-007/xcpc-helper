<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  darkTheme,
  dateZhCN,
  lightTheme,
  NConfigProvider,
  NMessageProvider,
  zhCN,
} from 'naive-ui'
import AppShell from '@/app/AppShell.vue'
import PlaceholderPage from '@/app/PlaceholderPage.vue'
import PrintBook from '@/features/printbook/PrintBookPage.vue'
import TemplateLibrary from '@/features/template/TemplateLibraryPage.vue'
import { useTheme } from '@/shared/composables/useTheme'
import { NAV_GROUPS, PLACEHOLDER_PAGES } from '@/app/nav'
import type { PageId, PlaceholderMeta } from '@/app/nav'
import { createThemeOverrides } from '@/app/theme'

const { mode, hue, isDark, modeIcon, modeLabel, cycleMode, setMode, setHue } = useTheme()

const activePage = ref<PageId>('lib')
const openGroups = ref<Record<string, boolean>>({ templates: true })

const placeholderMeta = computed<PlaceholderMeta>(() =>
  activePage.value === 'lib' ? PLACEHOLDER_PAGES.books : PLACEHOLDER_PAGES[activePage.value],
)

const pageMeta = computed(() => {
  const group = NAV_GROUPS.find(
    (g) => g.page === activePage.value || g.children?.some((c) => c.page === activePage.value),
  )
  if (!group) return { group: '', sub: '' }
  if (group.page === activePage.value) return { group: group.label, sub: '' }
  const child = group.children?.find((c) => c.page === activePage.value)
  return { group: group.label, sub: child?.label ?? '' }
})

const themeOverrides = computed(() => createThemeOverrides(!isDark.value, hue.value))

function navigate(page: PageId): void {
  activePage.value = page
  const group = NAV_GROUPS.find(
    (g) => g.page === page || g.children?.some((c) => c.page === page),
  )
  if (group) openGroups.value[group.id] = true
}

function toggleGroup(id: string): void {
  const group = NAV_GROUPS.find((g) => g.id === id)
  if (!group) return
  openGroups.value[id] = !openGroups.value[id]
  if (
    openGroups.value[id] &&
    group.children &&
    !group.children.some((c) => c.page === activePage.value)
  ) {
    activePage.value = group.children[0].page
  }
}

function onKeydown(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    if (activePage.value !== 'lib') navigate('lib')
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
        :active-page="activePage"
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
        <Transition name="page-swap" mode="out-in">
          <TemplateLibrary v-if="activePage === 'lib'" />
          <PrintBook v-else-if="activePage === 'books'" />
          <PlaceholderPage v-else :page="activePage" :meta="placeholderMeta" />
        </Transition>
      </AppShell>
    </n-message-provider>
  </n-config-provider>
</template>
