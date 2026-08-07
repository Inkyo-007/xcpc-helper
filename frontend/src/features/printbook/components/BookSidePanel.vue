<script setup lang="ts">
import { computed } from 'vue'
import { BookOpen, Pencil, Settings2, Trash2 } from 'lucide-vue-next'
import { NButton, NSelect } from 'naive-ui'
import BlockAddBar from '@/features/printbook/components/BlockAddBar.vue'
import TemplatePicker from '@/features/printbook/components/TemplatePicker.vue'
import type { BookBlockType, PrintBookSummary } from '@/features/printbook/types'
import type { SortMode, TemplateDetail, TemplateSummary } from '@/features/template/types'

const props = defineProps<{
  books: PrintBookSummary[]
  templates: TemplateSummary[]
  allTemplates: TemplateSummary[]
  details: Record<string, TemplateDetail>
  activeName: string | null
  blockCount: number
}>()

const emit = defineEmits<{
  'select-book': [name: string]
  'new-book': []
  settings: []
  rename: []
  'delete-book': []
  'add-block': [type: BookBlockType, after: number]
  'add-image': [file: File, after: number]
  'add-template': [templateId: string, version: string | null, after: number]
  'picker-query': [query: { category: string; keyword: string; sort: SortMode }]
  'request-detail': [templateId: string]
}>()

const selected = computed({
  get: () => props.activeName ?? '',
  set: (value: string) => {
    if (value === '__new__') emit('new-book')
    else if (value) emit('select-book', value)
  },
})

const bookOptions = computed(() => [
  { label: '＋ 新建打印册', value: '__new__' },
  // 下拉显示册名（身份标识）：封面标题可在"封面与选项"中独立设置，
  // 若显示标题会导致仅重命名册名时下拉框看起来"没有更新"
  ...props.books.map((b) => ({ label: b.name, value: b.name })),
])
</script>

<template>
  <div class="pb-side">
    <div class="pb-side-top">
      <div class="pb-book-switch">
        <BookOpen :size="15" class="pb-book-icon" />
        <n-select
          v-model:value="selected"
          class="pb-book-select"
          size="small"
          :options="bookOptions"
        />
      </div>
      <div class="pb-book-actions">
        <n-button quaternary size="small" title="重命名打印册" @click="emit('rename')">
          <template #icon><Pencil :size="14" /></template>
        </n-button>
        <n-button quaternary size="small" title="封面与选项设置" @click="emit('settings')">
          <template #icon><Settings2 :size="14" /></template>
        </n-button>
        <n-button
          quaternary
          size="small"
          title="删除打印册"
          class="pb-book-delete"
          @click="emit('delete-book')"
        >
          <template #icon><Trash2 :size="14" /></template>
        </n-button>
      </div>
    </div>

    <BlockAddBar
      :block-count="blockCount"
      @add="emit('add-block', $event.type, $event.after)"
      @add-image="emit('add-image', $event.file, $event.after)"
    />

    <div class="pb-picker-label">
      <span>模板库</span>
      <span class="pb-picker-label-count">{{ templates.length }}</span>
    </div>
    <TemplatePicker
      :templates="templates"
      :all-templates="allTemplates"
      :details="details"
      @add-template="emit('add-template', $event.templateId, $event.version, $event.after)"
      @query-change="emit('picker-query', $event)"
      @request-detail="emit('request-detail', $event)"
    />
  </div>
</template>

<style scoped>
.pb-side {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.pb-side-top {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex: none;
}

.pb-book-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.pb-book-icon {
  flex: none;
  color: var(--accent);
}

.pb-book-select {
  min-width: 0;
  flex: 1;
}

.pb-book-actions {
  display: flex;
  gap: 2px;
  flex: none;
}

.pb-book-delete:hover {
  color: #e5484d;
}

.pb-picker-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px 7px;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  flex: none;
}

.pb-picker-label-count {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--faint);
}
</style>
