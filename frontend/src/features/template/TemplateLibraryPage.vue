<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Check, ChevronRight, Flag, Inbox, Plus, RefreshCw, Search } from 'lucide-vue-next'
import { NAlert, NButton, NEmpty, NInput, NSelect, NSpin, NTooltip, useMessage } from 'naive-ui'
import DeleteConfirmModal from '@/shared/components/DeleteConfirmModal.vue'
import TemplateCreateModal from '@/features/template/components/TemplateCreateModal.vue'
import TemplateDetail from '@/features/template/components/TemplateDetail.vue'
import VersionFormModal from '@/features/template/components/VersionFormModal.vue'
import { useTemplates } from '@/features/template/store'
import { ROOT_VERSION_TOKEN } from '@/features/template/types'
import type {
  SortMode,
  TemplateDetail as TemplateDetailData,
  TemplateSummary,
  TemplateVariant,
} from '@/features/template/types'

const {
  templates,
  categories,
  diagnostics,
  listLoading,
  listError,
  initialized,
  init,
  loadList,
  loadDetail,
  reload,
  deleteTemplate,
  removeVersion,
  categoryHue,
  categoryName,
} = useTemplates()

const message = useMessage()
const query = ref('')
const category = ref('all')
const sortMode = ref<SortMode>('updated')
const activeId = ref<string | null>(null)
const catMenuOpen = ref(false)
const openVariants = ref<Record<string, boolean>>({})
const activeVariantId = ref<string | null>(null)
const reloading = ref(false)
const showCreate = ref(false)
const deletingTemplate = ref<TemplateDetailData | null>(null)
const deleteLoading = ref(false)
const versionForm = ref<{
  mode: 'create' | 'edit'
  templateId: string
  variant: TemplateVariant | null
} | null>(null)
const deletingVersion = ref<{ templateId: string; variant: TemplateVariant } | null>(null)
const versionDeleteLoading = ref(false)

/** 已加载的详情缓存（驱动右侧详情与列表中的副标签展开） */
const details = ref<Record<string, TemplateDetailData>>({})

const sortOptions = [
  { label: '按更新时间', value: 'updated' },
  { label: '按名称', value: 'name' },
  { label: '按优先级', value: 'priority' },
]

let debounceTimer: number | undefined
watch([query, category, sortMode], () => {
  window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    void loadList({ category: category.value, keyword: query.value, sort: sortMode.value })
  }, 200)
})

onMounted(() => {
  if (!initialized.value) {
    void init()
  } else {
    void loadList({ category: category.value, keyword: query.value, sort: sortMode.value })
  }
})

const activeTemplate = computed(
  () =>
    templates.value.find((template) => template.id === activeId.value) ??
    templates.value[0] ??
    null,
)

const activeDetail = computed(() => {
  const id = activeTemplate.value?.id
  return id ? (details.value[id] ?? null) : null
})

const activeDetailVariant = computed(() => {
  const detail = activeDetail.value
  if (!detail?.variants.length) return null
  return detail.variants.find((v) => v.id === activeVariantId.value) ?? detail.variants[0]
})

watch(
  activeTemplate,
  (template) => {
    if (!template) return
    if (template.variant_count > 1 && openVariants.value[template.id] === undefined) {
      openVariants.value[template.id] = true
    }
    void ensureDetail(template.id)
  },
  { immediate: true },
)

async function ensureDetail(id: string): Promise<TemplateDetailData | null> {
  if (details.value[id]) return details.value[id]
  const detail = await loadDetail(id)
  if (detail) details.value[id] = detail
  return detail
}

async function selectTemplate(template: TemplateSummary): Promise<void> {
  activeId.value = template.id
  for (const id of Object.keys(openVariants.value)) {
    if (id !== template.id) openVariants.value[id] = false
  }
  const opening = !openVariants.value[template.id]
  openVariants.value[template.id] = opening
  const detail = await ensureDetail(template.id)
  if (opening) {
    activeVariantId.value = detail?.variants[0]?.id ?? null
  } else {
    activeVariantId.value = null
  }
}

function selectVariant(template: TemplateSummary, variant: TemplateVariant): void {
  activeId.value = template.id
  for (const id of Object.keys(openVariants.value)) {
    if (id !== template.id) openVariants.value[id] = false
  }
  openVariants.value[template.id] = true
  activeVariantId.value = variant.id
}

function selectCategory(id: string): void {
  category.value = id
  catMenuOpen.value = false
}

function resetFilters(): void {
  query.value = ''
  category.value = 'all'
}

async function onReload(): Promise<void> {
  reloading.value = true
  try {
    await reload()
    for (const id of Object.keys(details.value)) {
      delete details.value[id]
    }
    if (activeTemplate.value) await ensureDetail(activeTemplate.value.id)
  } finally {
    reloading.value = false
  }
}

/** 新建空主标签成功：选中新模板（分类过滤随之切到其所属分类，保证立即可见） */
function onTemplateCreated(id: string): void {
  const cat = id.split('/')[0]
  if (category.value !== 'all' && category.value !== cat) {
    // 切到新模板所属分类，保证它立即可见；watch 会触发列表刷新
    category.value = cat
  }
  activeId.value = id
  activeVariantId.value = null
  void ensureDetail(id)
}

/** 空主标签的"删除模板"入口：打开确认弹窗 */
function onDeleteTemplate(): void {
  if (activeDetail.value) deletingTemplate.value = activeDetail.value
}

async function confirmDeleteTemplate(): Promise<void> {
  const target = deletingTemplate.value
  if (!target) return
  deleteLoading.value = true
  try {
    await deleteTemplate(target.id)
    message.success(`已删除模板「${target.name}」`)
    delete details.value[target.id]
    if (activeId.value === target.id) {
      activeId.value = null
      activeVariantId.value = null
    }
    deletingTemplate.value = null
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除失败，请重试')
  } finally {
    deleteLoading.value = false
  }
}

/** 展开区末尾的 + 按钮：为该模板新建版本 */
function onAddVersion(template: TemplateSummary): void {
  activeId.value = template.id
  for (const id of Object.keys(openVariants.value)) {
    if (id !== template.id) openVariants.value[id] = false
  }
  openVariants.value[template.id] = true
  void ensureDetail(template.id)
  versionForm.value = { mode: 'create', templateId: template.id, variant: null }
}

/** 详情页编辑按钮：编辑当前显示的版本 */
function onEditVersion(): void {
  const detail = activeDetail.value
  const variant = activeDetailVariant.value
  if (!detail || !variant) return
  versionForm.value = { mode: 'edit', templateId: detail.id, variant }
}

/** 详情页删除按钮：删除当前显示的版本（确认后物理删除） */
function onDeleteVersion(): void {
  const detail = activeDetail.value
  const variant = activeDetailVariant.value
  if (!detail || !variant) return
  deletingVersion.value = { templateId: detail.id, variant }
}

/** 版本表单保存成功：刷新详情缓存并选中刚保存的版本 */
async function onVersionSaved(detailId: string, versionName: string): Promise<void> {
  delete details.value[detailId]
  const detail = await ensureDetail(detailId)
  if (!detail) return
  activeId.value = detailId
  openVariants.value[detailId] = true
  const variant = detail.variants.find((v) => v.name === versionName)
  activeVariantId.value = variant?.id ?? detail.variants[0]?.id ?? null
}

async function confirmDeleteVersion(): Promise<void> {
  const target = deletingVersion.value
  if (!target) return
  versionDeleteLoading.value = true
  try {
    const token =
      target.variant.id === target.templateId ? ROOT_VERSION_TOKEN : target.variant.name
    await removeVersion(target.templateId, token)
    message.success(`已删除版本「${target.variant.name}」`)
    delete details.value[target.templateId]
    const detail = await ensureDetail(target.templateId)
    activeVariantId.value = detail?.variants[0]?.id ?? null
    deletingVersion.value = null
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除失败，请重试')
  } finally {
    versionDeleteLoading.value = false
  }
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
                  <span v-if="cat.count !== undefined" class="cat-count">{{ cat.count }}</span>
                  <Check v-if="category === cat.id" :size="14" class="cat-check" />
                </button>
              </div>
            </Transition>
          </div>
          <div class="tpl-tools">
            <n-tooltip>
              <template #trigger>
                <n-button
                  size="small"
                  quaternary
                  @click="showCreate = true"
                >
                  <template #icon><Plus :size="14" /></template>
                </n-button>
              </template>
              新增模板
            </n-tooltip>
            <n-tooltip>
              <template #trigger>
                <n-button
                  size="small"
                  quaternary
                  :loading="reloading"
                  @click="onReload"
                >
                  <template #icon><RefreshCw :size="14" /></template>
                </n-button>
              </template>
              手动刷新
            </n-tooltip>
            <n-select
              v-model:value="sortMode"
              class="sort-select"
              size="small"
              :options="sortOptions"
            />
            <span class="toolbar-meta">{{ templates.length }} 个模板</span>
          </div>
        </div>

        <n-alert
          v-if="diagnostics.length"
          type="warning"
          class="diag-alert"
          :bordered="false"
        >
          content/ 中存在 {{ diagnostics.length }} 处格式问题：{{ diagnostics[0].message }}（{{
            diagnostics[0].path
          }}）{{ diagnostics.length > 1 ? ' 等' : '' }}
        </n-alert>

        <n-alert v-if="listError" type="error" class="diag-alert" :bordered="false">
          {{ listError }}
          <n-button size="tiny" quaternary @click="onReload">重试</n-button>
        </n-alert>

        <n-spin :show="listLoading" class="tpl-list-spin">
          <div class="tpl-list">
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
                    <span class="tpl-meta">
                      <template v-if="template.updated"
                        >{{ template.updated }}<span class="tpl-meta-sep">·</span></template
                      >
                      <n-tooltip>
                        <template #trigger>
                          <span class="tpl-priority"
                            ><Flag :size="10" />{{ template.priority }}</span
                          >
                        </template>
                        优先级 {{ template.priority }}（多版本取最大值）
                      </n-tooltip>
                    </span>
                  </span>
                  <ChevronRight class="tpl-chev" :size="14" />
                </button>
                <div
                  v-if="details[template.id]"
                  class="tpl-variants"
                >
                  <button
                    v-for="variant in details[template.id]?.variants ?? []"
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
                  <n-tooltip>
                    <template #trigger>
                      <button
                        type="button"
                        class="tpl-variant tpl-add"
                        @click="onAddVersion(template)"
                      >
                        <Plus :size="12" />
                      </button>
                    </template>
                    新增版本
                  </n-tooltip>
                </div>
              </div>
            </TransitionGroup>
            <n-empty
              v-if="!templates.length && !listLoading"
              class="empty-panel"
              description="没有匹配的模板"
            >
              <template #extra>
                <n-button size="small" quaternary @click="resetFilters">清除筛选</n-button>
              </template>
            </n-empty>
          </div>
        </n-spin>
      </div>

      <Transition name="detail-swap" mode="out-in">
        <TemplateDetail
          v-if="activeDetail"
          :key="activeDetail.id"
          :detail="activeDetail"
          :variant="activeDetailVariant"
          :category-name="categoryName(activeDetail.cat)"
          @delete-template="onDeleteTemplate"
          @edit-version="onEditVersion"
          @delete-version="onDeleteVersion"
        />
        <div v-else class="detail empty-detail">
          <Inbox :size="32" />
          <span>{{ listLoading ? '加载中…' : '未选择模板' }}</span>
        </div>
      </Transition>
    </div>

    <TemplateCreateModal v-model:show="showCreate" @created="onTemplateCreated" />
    <DeleteConfirmModal
      :show="deletingTemplate !== null"
      title="删除模板"
      :target="deletingTemplate?.id ?? ''"
      :loading="deleteLoading"
      @update:show="deletingTemplate = null"
      @confirm="confirmDeleteTemplate"
    />
    <VersionFormModal
      v-if="versionForm"
      :show="versionForm !== null"
      :mode="versionForm.mode"
      :template-id="versionForm.templateId"
      :variant="versionForm.variant"
      @update:show="versionForm = null"
      @saved="onVersionSaved"
    />
    <DeleteConfirmModal
      :show="deletingVersion !== null"
      title="删除版本"
      :target="
        deletingVersion ? `${deletingVersion.templateId}/${deletingVersion.variant.name}` : ''
      "
      :loading="versionDeleteLoading"
      @update:show="deletingVersion = null"
      @confirm="confirmDeleteVersion"
    />
  </div>
</template>
