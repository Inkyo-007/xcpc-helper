<script setup lang="ts">
import { ref } from 'vue'
import {
  Braces,
  FileText,
  GripVertical,
  Heading1,
  Image as ImageIcon,
  Inbox,
  Pencil,
  SeparatorHorizontal,
  Trash2,
} from 'lucide-vue-next'
import { NButton, NEmpty, NTooltip } from 'naive-ui'
import type { BookBlock, BookBlockType } from '@/features/printbook/types'

defineProps<{
  blocks: BookBlock[]
}>()

const emit = defineEmits<{
  edit: [block: BookBlock]
  delete: [id: string]
  move: [from: number, to: number]
}>()

const listEl = ref<HTMLDivElement | null>(null)
const dragIndex = ref<number | null>(null)
const dropIndex = ref<number | null>(null)

function typeMeta(block: BookBlock): { label: string; level?: number; detail: string } {
  if (block.type === 'heading') {
    return { label: '章节', level: block.heading_level, detail: `H${block.heading_level}` }
  }
  if (block.type === 'template') {
    const resolved = block.resolved
    return {
      label: '模板',
      level: block.heading_level,
      detail: `${resolved?.version_name ?? '未知版本'} · ${resolved?.lang ?? '?'}`,
    }
  }
  if (block.type === 'markdown') {
    return { label: '文字', detail: 'Markdown' }
  }
  if (block.type === 'image') {
    return { label: '图片', detail: block.width }
  }
  return { label: '分页', detail: '新页开始' }
}

function blockTitle(block: BookBlock): string {
  if (block.type === 'heading') return block.title || '未命名章节'
  if (block.type === 'template') return block.title ?? block.resolved?.name ?? '未知模板'
  if (block.type === 'markdown') return block.title ?? '文字说明'
  if (block.type === 'image') return block.caption ?? '图片'
  return '分页符'
}

function typeIcon(type: BookBlockType) {
  if (type === 'heading') return Heading1
  if (type === 'template') return Braces
  if (type === 'markdown') return FileText
  if (type === 'image') return ImageIcon
  return SeparatorHorizontal
}

function onDragStart(event: DragEvent, index: number): void {
  dragIndex.value = index
  dropIndex.value = null
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function onListDragOver(event: DragEvent): void {
  if (dragIndex.value === null) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  const list = listEl.value
  if (!list) return
  const rect = list.getBoundingClientRect()
  const threshold = 56
  if (event.clientY < rect.top + threshold) {
    list.scrollTop -= 12
  } else if (event.clientY > rect.bottom - threshold) {
    list.scrollTop += 12
  }
  const rows = list.querySelectorAll<HTMLElement>('[data-entry-index]')
  for (const row of rows) {
    const bounds = row.getBoundingClientRect()
    if (event.clientY >= bounds.top && event.clientY < bounds.bottom) {
      const index = Number(row.dataset.entryIndex)
      dropIndex.value = event.clientY < bounds.top + bounds.height / 2 ? index : index + 1
      break
    }
  }
}

function onDragEnd(): void {
  const from = dragIndex.value
  const to = dropIndex.value
  dragIndex.value = null
  dropIndex.value = null
  if (from === null || to === null || to === from || to === from + 1) return
  emit('move', from, to)
}
</script>

<template>
  <div class="pb-entries">
    <div class="pb-entries-head">
      <span class="pb-entries-title">当前册条目</span>
      <span class="pb-entries-count">{{ blocks.length }}</span>
      <GripVertical :size="14" class="pb-entries-drag-hint" />
    </div>
    <div
      ref="listEl"
      class="pb-entries-list"
      @dragover="onListDragOver"
      @drop.prevent="onDragEnd"
    >
      <TransitionGroup name="tpl-list" tag="div" class="pb-entries-inner">
        <div
          v-for="(block, index) in blocks"
          :key="block.id"
          class="pb-entry"
          :class="{
            'pb-entry-dragging': dragIndex === index,
            'pb-entry-drop': dropIndex === index,
          }"
          :data-entry-index="index"
          draggable="true"
          @dragstart="onDragStart($event, index)"
          @dragend="onDragEnd"
        >
          <GripVertical :size="15" class="pb-entry-grip" />
          <span class="pb-entry-idx">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="pb-entry-icon">
            <component :is="typeIcon(block.type)" :size="15" />
          </span>
          <span class="pb-entry-cell">
            <span class="pb-entry-name">
              <span class="pb-entry-text">{{ blockTitle(block) }}</span>
              <span class="pb-type-badge">{{ typeMeta(block).label }}</span>
              <span v-if="typeMeta(block).level" class="pb-level-badge">
                H{{ typeMeta(block).level }}
              </span>
            </span>
            <span class="pb-entry-meta">{{ typeMeta(block).detail }}</span>
          </span>
          <span class="pb-entry-actions">
            <n-tooltip v-if="block.type !== 'page_break'">
              <template #trigger>
                <n-button quaternary size="tiny" @click="emit('edit', block)">
                  <template #icon><Pencil :size="13" /></template>
                </n-button>
              </template>
              编辑
            </n-tooltip>
            <n-tooltip>
              <template #trigger>
                <n-button
                  quaternary
                  size="tiny"
                  class="pb-entry-delete"
                  @click="emit('delete', block.id)"
                >
                  <template #icon><Trash2 :size="13" /></template>
                </n-button>
              </template>
              删除
            </n-tooltip>
          </span>
        </div>
      </TransitionGroup>
      <div v-if="dropIndex === blocks.length" class="pb-drop-tail"></div>
      <n-empty v-if="!blocks.length" class="pb-entries-empty" description="当前册为空">
        <template #icon><Inbox :size="30" /></template>
      </n-empty>
    </div>
  </div>
</template>

<style scoped>
.pb-entries {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.pb-entries-head {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 42px;
  padding: 0 14px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex: none;
}

.pb-entries-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--text);
}

.pb-entries-count {
  font-family: var(--font-mono);
  font-size: 11px;
  min-width: 20px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  border-radius: 99px;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.pb-entries-drag-hint {
  margin-left: auto;
  color: var(--faint);
}

.pb-entries-list {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.pb-entries-inner {
  min-height: 100%;
  padding-bottom: 4px;
}

.pb-entry {
  position: relative;
  display: grid;
  grid-template-columns: 18px 26px 30px 1fr auto;
  align-items: center;
  gap: 8px;
  min-height: 54px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  cursor: grab;
  transition: background 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;
}

.pb-entry:hover {
  background: var(--surface-2);
  transform: translateX(2px);
}

.pb-entry:active {
  cursor: grabbing;
}

.pb-entry-dragging {
  opacity: 0.42;
  background: var(--accent-softer);
}

.pb-entry-drop::before {
  content: "";
  position: absolute;
  left: 6px;
  right: 6px;
  top: -2px;
  height: 2px;
  border-radius: 99px;
  background: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
  pointer-events: none;
}

.pb-drop-tail {
  position: absolute;
  left: 6px;
  right: 6px;
  bottom: 6px;
  height: 2px;
  border-radius: 99px;
  background: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
  pointer-events: none;
}

.pb-entry-grip {
  color: var(--faint);
  transition: color 0.16s ease;
}

.pb-entry:hover .pb-entry-grip {
  color: var(--accent);
}

.pb-entry-idx {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--faint);
  text-align: center;
  user-select: none;
}

.pb-entry-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--accent-softer);
  color: var(--accent-strong);
  flex: none;
}

.pb-entry-cell {
  min-width: 0;
}

.pb-entry-name {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.pb-entry-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.pb-type-badge,
.pb-level-badge {
  flex: none;
  font-family: var(--font-mono);
  font-size: 10px;
  height: 17px;
  display: inline-flex;
  align-items: center;
  padding: 0 6px;
  border-radius: 99px;
}

.pb-type-badge {
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--muted);
}

.pb-level-badge {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.pb-entry-meta {
  display: block;
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pb-entry-actions {
  display: flex;
  gap: 2px;
  flex: none;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.pb-entry:hover .pb-entry-actions {
  opacity: 1;
}

.pb-entry-delete {
  color: var(--muted);
}

.pb-entry-delete:hover {
  color: #e5484d;
}

.pb-entries-empty {
  position: absolute;
  inset: 0;
}
</style>
