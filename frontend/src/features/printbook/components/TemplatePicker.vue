<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, ChevronRight, Flag, Plus, Search } from 'lucide-vue-next'
import { NButton, NEmpty, NInput, NSelect, NTooltip } from 'naive-ui'
import type { SortMode, TemplateDetail, TemplateSummary, TemplateVariant } from '@/features/template/types'

const props = defineProps<{
  templates: TemplateSummary[]
  /** 全量模板摘要：分类计数不受当前筛选影响 */
  allTemplates: TemplateSummary[]
  /** 已拉取的模板详情缓存；展开版本列表前由 request-detail 触发加载 */
  details: Record<string, TemplateDetail>
  /** 插入位置：-1 末尾，0 头部，N 第 N 个条目之后 */
  after: number
}>()

const emit = defineEmits<{
  'add-template': [{ templateId: string; version: string | null; after: number }]
  /** 搜索/分类/排序变化（父级 200ms 防抖后走后端查询） */
  'query-change': [{ category: string; keyword: string; sort: SortMode }]
  /** 展开某模板的版本列表前请求其详情 */
  'request-detail': [templateId: string]
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
  for (const t of props.allTemplates) {
    counts.set(t.cat, (counts.get(t.cat) ?? 0) + 1)
  }
  return [
    { id: 'all', name: '全部', count: props.allTemplates.length, hue: null as number | null },
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

// 搜索/分类/排序均由后端完成：本地变更 200ms 防抖后通知父级查询
let queryTimer: ReturnType<typeof setTimeout> | null = null

watch([query, category, sortMode], () => {
  if (queryTimer) clearTimeout(queryTimer)
  queryTimer = setTimeout(() => {
    emit('query-change', {
      category: category.value,
      keyword: query.value.trim(),
      sort: sortMode.value,
    })
  }, 200)
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
  if (openVariants.value[template.id]) emit('request-detail', template.id)
}

function addVariant(template: TemplateSummary, variant: TemplateVariant): void {
  const version = variant.id === template.id ? '~' : variant.name
  activeId.value = template.id
  emit('add-template', { templateId: template.id, version, after: props.after })
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
        <span class="toolbar-meta">{{ templates.length }} 个模板</span>
      </div>
    </div>

    <div class="tpl-list pb-picker-list">
      <TransitionGroup name="tpl-list" tag="div" class="tpl-list-inner">
        <div
          v-for="(template, index) in templates"
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
                <n-tooltip>
                  <template #trigger>
                    <span class="tpl-priority">
                      <Flag :size="10" />{{ template.priority }}
                    </span>
                  </template>
                  优先级 {{ template.priority }}
                </n-tooltip>
              </span>
            </span>
            <ChevronRight class="tpl-chev" :size="14" />
          </button>
          <div v-if="openVariants[template.id] && details[template.id]" class="tpl-variants">
            <button
              v-for="variant in details[template.id]?.variants ?? []"
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
        v-if="!templates.length"
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
