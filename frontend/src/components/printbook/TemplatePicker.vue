<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, ChevronRight, Flag, Plus, Search } from 'lucide-vue-next'
import { NButton, NEmpty, NInput, NSelect } from 'naive-ui'
import { MOCK_TEMPLATE_DETAIL_MAP } from '@/mock/printbook'
import type { SortMode, TemplateSummary, TemplateVariant } from '@/types'

const props = defineProps<{
  templates: TemplateSummary[]
}>()

const emit = defineEmits<{
  'add-template': [{ templateId: string; version: string | null; after: number }]
}>()

const HUE_PALETTE = [160, 25, 280, 200, 340, 80, 120, 300, 0, 220]

const query = ref('')
const category = ref('all')
const sortMode = ref<SortMode>('updated')
const catMenuOpen = ref(false)
const openVariants = ref<Record<string, boolean>>({})
const activeId = ref<string | null>(null)

const categories = computed(() => {
  const counts = new Map<string, number>()
  for (const t of props.templates) {
    counts.set(t.cat, (counts.get(t.cat) ?? 0) + 1)
  }
  return [
    { id: 'all', name: '全部', count: props.templates.length, hue: null as number | null },
    ...[...counts.entries()].map(([id, count], index) => ({
      id,
      name: id,
      count,
      hue: HUE_PALETTE[index % HUE_PALETTE.length],
    })),
  ]
})

const SORT_OPTIONS = [
  { label: '按更新时间', value: 'updated' },
  { label: '按名称', value: 'name' },
  { label: '按优先级', value: 'priority' },
]

const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  let list = props.templates.filter((t) => {
    if (category.value !== 'all' && t.cat !== category.value) return false
    if (!keyword) return true
    const detail = MOCK_TEMPLATE_DETAIL_MAP[t.id]
    const haystack = [
      t.name,
      t.cat,
      ...t.tags,
      detail?.desc ?? '',
      ...(detail?.variants.map((v) => v.body + ' ' + v.code) ?? []),
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(keyword)
  })
  const sorted = [...list]
  if (sortMode.value === 'name') {
    sorted.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  } else if (sortMode.value === 'priority') {
    sorted.sort((a, b) => b.priority - a.priority || a.name.localeCompare(b.name, 'zh-CN'))
  } else {
    sorted.sort(
      (a, b) =>
        (b.updated ?? '').localeCompare(a.updated ?? '') ||
        a.name.localeCompare(b.name, 'zh-CN'),
    )
  }
  return sorted
})

function categoryHue(cat: string): number {
  return categories.value.find((c) => c.id === cat)?.hue ?? 160
}

function selectCategory(id: string): void {
  category.value = id
  catMenuOpen.value = false
}

function resetFilters(): void {
  query.value = ''
  category.value = 'all'
}

function toggleTemplate(template: TemplateSummary): void {
  activeId.value = template.id
  for (const id of Object.keys(openVariants.value)) {
    if (id !== template.id) openVariants.value[id] = false
  }
  openVariants.value[template.id] = !openVariants.value[template.id]
}

function addVariant(template: TemplateSummary, variant: TemplateVariant): void {
  const version = variant.id === template.id ? '~' : variant.name
  activeId.value = template.id
  emit('add-template', { templateId: template.id, version, after: 0 })
}
</script>

<template>
  <div class="pb-picker">
    <div class="tpl-panel-head">
      <div class="search-wrap" @mouseover="catMenuOpen = true" @mouseleave="catMenuOpen = false">
        <n-input
          v-model:value="query"
          class="search-input"
          clearable
          placeholder="搜索模板、说明或代码…"
        >
          <template #prefix>
            <Search :size="15" />
          </template>
        </n-input>
        <Transition name="cat-drop">
          <div v-if="catMenuOpen" class="cat-dropdown" role="menu" aria-label="按分类筛选">
            <button
              v-for="cat in categories"
              :key="cat.id"
              type="button"
              class="cat-option"
              :class="{ active: category === cat.id }"
              role="menuitem"
              :aria-checked="category === cat.id"
              @click="selectCategory(cat.id)"
            >
              <span
                class="cat-option-dot"
                :style="
                  cat.hue
                    ? { background: `hsl(${cat.hue} 60% 50%)` }
                    : { background: 'var(--accent)' }
                "
              ></span>
              <span>{{ cat.name }}</span>
              <span class="cat-count">{{ cat.count }}</span>
              <Check v-if="category === cat.id" :size="14" class="cat-check" />
            </button>
          </div>
        </Transition>
      </div>
      <div class="tpl-tools">
        <n-select v-model:value="sortMode" class="sort-select" size="small" :options="SORT_OPTIONS" />
        <span class="toolbar-meta">{{ filtered.length }} 个模板</span>
      </div>
    </div>

    <div class="tpl-list pb-picker-list">
      <TransitionGroup name="tpl-list" tag="div" class="tpl-list-inner">
        <div
          v-for="(template, index) in filtered"
          :key="template.id"
          class="tpl-item"
          :class="{ open: openVariants[template.id] }"
        >
          <button
            type="button"
            class="tpl-row"
            :class="{ active: activeId === template.id }"
            @click="toggleTemplate(template)"
          >
            <span class="tpl-idx">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="tpl-cell">
              <span class="tpl-name">
                <span
                  class="cat-dot"
                  :style="{ background: `hsl(${categoryHue(template.cat)} 55% 50%)` }"
                ></span>
                <span class="tpl-name-text">{{ template.name }}</span>
              </span>
              <span class="tpl-meta">
                <template v-if="template.updated"
                  >{{ template.updated }}<span class="tpl-meta-sep">·</span></template
                >
                <span class="tpl-priority" :title="`优先级 ${template.priority}`">
                  <Flag :size="10" />{{ template.priority }}
                </span>
              </span>
            </span>
            <ChevronRight class="tpl-chev" :size="14" />
          </button>
          <div v-if="MOCK_TEMPLATE_DETAIL_MAP[template.id]" class="tpl-variants">
            <button
              v-for="variant in MOCK_TEMPLATE_DETAIL_MAP[template.id]?.variants ?? []"
              :key="variant.id"
              type="button"
              class="tpl-variant"
              @click="addVariant(template, variant)"
            >
              <Plus :size="11" class="pb-variant-add" />
              <span class="variant-name">{{ variant.name }}</span>
              <span class="variant-lang">{{ variant.lang }}</span>
            </button>
          </div>
        </div>
      </TransitionGroup>
      <n-empty
        v-if="!filtered.length"
        class="empty-panel"
        description="没有匹配的模板"
      >
        <template #extra>
          <n-button size="small" quaternary @click="resetFilters">清除筛选</n-button>
        </template>
      </n-empty>
    </div>
  </div>
</template>

<style scoped>
.pb-picker {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.pb-picker-list {
  flex: 1;
}

.pb-variant-add {
  color: var(--faint);
  transition: color 0.16s ease, transform 0.16s ease;
}

.tpl-variant:hover .pb-variant-add {
  color: var(--accent);
  transform: scale(1.15);
}

.cat-count {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--faint);
}
</style>
