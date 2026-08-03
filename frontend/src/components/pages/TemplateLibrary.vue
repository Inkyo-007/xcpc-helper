<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, ChevronRight, Inbox, Search } from 'lucide-vue-next'
import { NButton, NEmpty, NInput, NSelect } from 'naive-ui'
import { CATEGORIES, categoryHue } from '@/data/categories'
import TemplateDetail from '@/components/TemplateDetail.vue'
import type { CategoryId, SortMode, Template, TemplateVariant } from '@/types'

const props = defineProps<{
  templates: Template[]
}>()

const query = ref('')
const category = ref<CategoryId>('all')
const sortMode = ref<SortMode>('updated')
const activeId = ref<number | null>(null)
const catMenuOpen = ref(false)
const openVariants = ref<Record<number, boolean>>({})
const activeVariant = ref<TemplateVariant | null>(null)

const sortOptions = [
  { label: '按更新时间', value: 'updated' },
  { label: '按名称', value: 'name' },
  { label: '按优先级', value: 'priority' },
]

const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const matched = props.templates.filter((template) => {
    const catMatched = category.value === 'all' || template.cat === category.value
    const haystack = [template.name, template.desc, template.code, template.src, template.tags.join(' ')]
      .join(' ')
      .toLowerCase()
    return catMatched && (!keyword || haystack.includes(keyword))
  })

  return [...matched].sort((a, b) => {
    if (sortMode.value === 'name') return a.name.localeCompare(b.name, 'zh-Hans-CN')
    if (sortMode.value === 'priority') {
      const diff = (b.priority ?? 0) - (a.priority ?? 0)
      if (diff !== 0) return diff
      return a.updated < b.updated ? 1 : -1
    }
    return a.updated < b.updated ? 1 : -1
  })
})

const activeTemplate = computed(
  () => filtered.value.find((template) => template.id === activeId.value) ?? filtered.value[0] ?? null,
)

const activeDetailVariant = computed(() => {
  const template = activeTemplate.value
  if (!template?.variants?.length) return null
  return (
    template.variants.find((variant) => variant.id === activeVariant.value?.id) ??
    template.variants[0]
  )
})

const activeVariantId = computed(() => activeDetailVariant.value?.id ?? null)

watch(
  activeTemplate,
  (template) => {
    if (template?.variants?.length && openVariants.value[template.id] === undefined) {
      openVariants.value[template.id] = true
    }
  },
  { immediate: true },
)

function selectTemplate(template: Template): void {
  activeId.value = template.id
  for (const id of Object.keys(openVariants.value)) {
    if (Number(id) !== template.id) {
      openVariants.value[Number(id)] = false
    }
  }
  if (!template.variants?.length) {
    activeVariant.value = null
    return
  }
  const opening = !openVariants.value[template.id]
  openVariants.value[template.id] = opening
  if (opening) {
    activeVariant.value = template.variants[0]
  } else {
    activeVariant.value = null
  }
}

function selectVariant(template: Template, variant: TemplateVariant): void {
  activeId.value = template.id
  for (const id of Object.keys(openVariants.value)) {
    if (Number(id) !== template.id) {
      openVariants.value[Number(id)] = false
    }
  }
  openVariants.value[template.id] = true
  activeVariant.value = variant
}

function selectCategory(id: CategoryId): void {
  category.value = id
  catMenuOpen.value = false
}

function resetFilters(): void {
  query.value = ''
  category.value = 'all'
}
</script>

<template>
  <div class="lib-page">
    <div class="lib-content">
      <div class="tpl-panel">
        <div class="tpl-panel-head">
          <div
            class="search-wrap"
            @mouseover="catMenuOpen = true"
            @mouseleave="catMenuOpen = false"
          >
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
              <div
                v-if="catMenuOpen"
                class="cat-dropdown"
                role="menu"
                aria-label="按分类筛选"
              >
                <button
                  v-for="cat in CATEGORIES"
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
                  <Check v-if="category === cat.id" :size="14" class="cat-check" />
                </button>
              </div>
            </Transition>
          </div>
          <div class="tpl-tools">
            <n-select
              v-model:value="sortMode"
              class="sort-select"
              size="small"
              :options="sortOptions"
            />
            <span class="toolbar-meta">{{ filtered.length }} / {{ templates.length }} 个模板</span>
          </div>
        </div>

        <div class="tpl-list">
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
                :class="{ active: template.id === activeTemplate?.id }"
                @click="selectTemplate(template)"
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
                  <span class="tpl-meta">{{ template.updated }}</span>
                </span>
                <ChevronRight v-if="template.variants?.length" class="tpl-chev" :size="14" />
              </button>
              <div v-if="template.variants?.length" class="tpl-variants">
                <button
                  v-for="variant in template.variants"
                  :key="variant.id"
                  type="button"
                  class="tpl-variant"
                  :class="{
                    active:
                      activeVariantId === variant.id && template.id === activeTemplate?.id,
                  }"
                  @click="selectVariant(template, variant)"
                >
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

      <Transition name="detail-swap" mode="out-in">
        <TemplateDetail
          v-if="activeTemplate"
          :key="activeTemplate.id"
          :template="activeTemplate"
          :variant="activeDetailVariant"
        />
        <div v-else class="detail empty-detail">
          <Inbox :size="32" />
          <span>未选择模板</span>
        </div>
      </Transition>
    </div>
  </div>
</template>
