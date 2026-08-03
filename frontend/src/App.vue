<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  darkTheme,
  dateZhCN,
  lightTheme,
  NConfigProvider,
  NMessageProvider,
  zhCN,
  type GlobalThemeOverrides,
} from 'naive-ui'
import SideNav from '@/components/SideNav.vue'
import TopBar from '@/components/TopBar.vue'
import PlaceholderPage from '@/components/pages/PlaceholderPage.vue'
import TemplateLibrary from '@/components/pages/TemplateLibrary.vue'
import { useTheme } from '@/composables/useTheme'
import { useTemplates } from '@/composables/useTemplates'
import { NAV_GROUPS, PLACEHOLDER_PAGES } from '@/data/nav'
import type { PageId, PlaceholderMeta } from '@/types'

const { mode, hue, isDark, modeIcon, modeLabel, cycleMode, setMode, setHue } = useTheme()
const { templates } = useTemplates()

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

const themeOverrides = computed<GlobalThemeOverrides>(() => {
  const light = !isDark.value
  const accent = `hsl(${hue.value}, 68%, ${light ? 48 : 24}%)`
  const accentHover = `hsl(${hue.value}, 72%, ${light ? 36 : 32}%)`
  const accentPressed = `hsl(${hue.value}, 70%, ${light ? 40 : 28}%)`
  const accentSoft = `hsla(${hue.value}, 60%, 40%, 0.16)`

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
})

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
      <div class="app-shell">
        <SideNav
          :active-page="activePage"
          :open-groups="openGroups"
          @navigate="navigate"
          @toggle="toggleGroup"
        />
        <main class="main-pane">
          <TopBar
            :page-meta="pageMeta"
            :mode="mode"
            :mode-icon="modeIcon"
            :mode-label="modeLabel"
            :hue="hue"
            @cycle-theme="cycleMode"
            @set-mode="setMode"
            @set-hue="setHue"
          />
          <section class="page-stage">
            <Transition name="page-swap" mode="out-in">
              <TemplateLibrary
                v-if="activePage === 'lib'"
                :templates="templates"
              />
              <PlaceholderPage v-else :page="activePage" :meta="placeholderMeta" />
            </Transition>
          </section>
        </main>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>
