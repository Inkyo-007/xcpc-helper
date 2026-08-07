<script setup lang="ts">
import { ref, watch } from 'vue'
import { FileText, Heading1, ImagePlus, SeparatorHorizontal } from 'lucide-vue-next'
import { NButton, NInputNumber } from 'naive-ui'
import type { BookBlockType } from '@/types'

const props = defineProps<{
  blockCount: number
}>()

const emit = defineEmits<{
  add: [{ type: BookBlockType; after: number }]
  'add-image': [{ file: File; after: number }]
}>()

const after = ref(0)
const fileInput = ref<HTMLInputElement | null>(null)

watch(
  () => props.blockCount,
  (count) => {
    if (after.value > count) after.value = count
  },
)

function add(type: BookBlockType): void {
  emit('add', { type, after: after.value })
}

function pickImage(): void {
  fileInput.value?.click()
}

function onFilePicked(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('add-image', { file, after: after.value })
  input.value = ''
}
</script>

<template>
  <div class="pb-addbar">
    <div class="pb-addbar-row">
      <div class="pb-add-actions">
        <n-button
          class="pb-add-btn"
          quaternary
          size="small"
          title="添加章节标题块"
          @click="add('heading')"
        >
          <template #icon><Heading1 :size="15" /></template>
        </n-button>
        <n-button
          class="pb-add-btn"
          quaternary
          size="small"
          title="添加文字说明块"
          @click="add('markdown')"
        >
          <template #icon><FileText :size="15" /></template>
        </n-button>
        <n-button class="pb-add-btn" quaternary size="small" title="添加图片块" @click="pickImage">
          <template #icon><ImagePlus :size="15" /></template>
        </n-button>
        <n-button
          class="pb-add-btn"
          quaternary
          size="small"
          title="添加分页符"
          @click="add('page_break')"
        >
          <template #icon><SeparatorHorizontal :size="15" /></template>
        </n-button>
      </div>
      <div class="pb-insert">
        <span class="pb-insert-label">插入位置</span>
        <n-input-number
          v-model:value="after"
          class="pb-insert-input"
          size="small"
          :min="0"
          :max="blockCount"
          title="0 表示末尾，N 表示第 N 个条目之后"
        />
      </div>
    </div>
    <input
      ref="fileInput"
      type="file"
      accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
      hidden
      @change="onFilePicked"
    />
  </div>
</template>

<style scoped>
.pb-addbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.pb-addbar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.pb-add-actions {
  display: flex;
  gap: 4px;
  flex: none;
}

.pb-add-btn {
  --n-height: 30px;
  width: 30px;
  padding: 0;
  transition: color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.pb-add-btn:hover {
  color: var(--accent);
  transform: translateY(-1px);
}

.pb-insert {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  min-width: 0;
}

.pb-insert-label {
  flex: none;
  font-size: 11.5px;
  color: var(--muted);
  white-space: nowrap;
}

.pb-insert-input {
  width: 86px;
}

</style>
