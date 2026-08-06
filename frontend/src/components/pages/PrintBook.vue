<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'
import DeleteConfirmModal from '@/components/DeleteConfirmModal.vue'
import BookNameModal from '@/components/printbook/BookNameModal.vue'
import BookSettingsModal from '@/components/printbook/BookSettingsModal.vue'
import BookSidePanel from '@/components/printbook/BookSidePanel.vue'
import EntryEditorModal from '@/components/printbook/EntryEditorModal.vue'
import EntryList from '@/components/printbook/EntryList.vue'
import BookPreview from '@/components/printbook/preview/BookPreview.vue'
import { usePrintBooks } from '@/composables/usePrintBooks'
import type {
  BookBlock,
  BookBlockType,
  PrintBookCover,
  PrintBookOptions,
  PrintBookSummary,
} from '@/types'

const message = useMessage()
const {
  books,
  templates,
  activeBook,
  activeDetail,
  headingLevel,
  templateLevel,
  rememberHeadingLevel,
  rememberTemplateLevel,
  selectBook,
  createBook,
  renameBook,
  deleteBook,
  updateSettings,
  addBlock,
  addImage,
  addTemplate,
  updateBlock,
  removeBlock,
  moveBlock,
} = usePrintBooks()

const showBookName = ref(false)
const bookNameMode = ref<'create' | 'rename'>('create')
const showSettings = ref(false)
const editingBlock = ref<BookBlock | null>(null)
const deletingBook = ref<PrintBookSummary | null>(null)

const blockCount = computed(() => activeDetail.value?.blocks.length ?? 0)
const blocks = computed(() => activeDetail.value?.blocks ?? [])

function onAddBlock(type: BookBlockType, after: number): void {
  addBlock(type, after)
}

function onAddImage(file: File, after: number): void {
  addImage(file, after)
}

function onAddTemplate(templateId: string, version: string | null, after: number): void {
  addTemplate(templateId, version, after)
}

function onSaveBlock(block: BookBlock): void {
  updateBlock(block)
}

function onBookCreated(name: string, title: string): void {
  const result = createBook(name, title)
  if (result.ok) {
    message.success(`已创建打印册「${name}」`)
  } else {
    message.error(result.message ?? '创建失败')
  }
}

function onBookRenamed(name: string): void {
  const book = activeBook.value
  if (!book) return
  const result = renameBook(book.name, name)
  if (result.ok) {
    message.success(`已重命名为「${name}」`)
  } else {
    message.error(result.message ?? '重命名失败')
  }
}

function onSettingsSaved(
  cover: PrintBookCover,
  options: PrintBookOptions,
  headingLevelValue: number,
  templateLevelValue: number,
): void {
  const book = activeBook.value
  if (!book) return
  updateSettings(book.name, cover, options)
  rememberHeadingLevel(headingLevelValue)
  rememberTemplateLevel(templateLevelValue)
  message.success('已保存封面与选项')
}

function confirmDeleteBook(): void {
  const book = deletingBook.value
  if (!book) return
  deleteBook(book.name)
  message.success(`已删除打印册「${book.title || book.name}」`)
  deletingBook.value = null
}
</script>

<template>
  <div class="pb-page">
    <div class="pb-content">
      <BookSidePanel
        class="pb-panel pb-panel-left"
        :books="books"
        :templates="templates"
        :active-name="activeBook?.name ?? null"
        :block-count="blockCount"
        @select-book="selectBook"
        @new-book="bookNameMode = 'create'; showBookName = true"
        @settings="showSettings = true"
        @rename="bookNameMode = 'rename'; showBookName = true"
        @delete-book="deletingBook = activeBook"
        @add-block="onAddBlock"
        @add-image="onAddImage"
        @add-template="onAddTemplate"
      />

      <EntryList
        class="pb-panel pb-panel-mid"
        :blocks="blocks"
        @edit="editingBlock = $event"
        @delete="removeBlock"
        @move="moveBlock"
      />

      <BookPreview class="pb-panel pb-panel-right" :detail="activeDetail" />
    </div>

    <BookNameModal
      v-model:show="showBookName"
      :mode="bookNameMode"
      :initial-name="bookNameMode === 'rename' ? (activeBook?.name ?? '') : ''"
      :initial-title="''"
      @submit="
        (name, title) =>
          bookNameMode === 'create' ? onBookCreated(name, title) : onBookRenamed(name)
      "
    />
    <BookSettingsModal
      v-model:show="showSettings"
      :book="activeDetail"
      :heading-level="headingLevel"
      :template-level="templateLevel"
      @save="onSettingsSaved"
    />
    <EntryEditorModal
      :show="editingBlock !== null"
      :block="editingBlock"
      @save="onSaveBlock"
      @update:show="editingBlock = null"
    />
    <DeleteConfirmModal
      :show="deletingBook !== null"
      title="删除打印册"
      :target="deletingBook?.title || deletingBook?.name || ''"
      :loading="false"
      @update:show="deletingBook = null"
      @confirm="confirmDeleteBook"
    />
  </div>
</template>

<style scoped>
.pb-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  animation: page-in 0.4s ease both;
}

.pb-content {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(300px, 330px) minmax(330px, 390px) 1fr;
  padding: 4px 20px 18px;
}

.pb-panel {
  min-width: 0;
  min-height: 0;
  border: 1px solid var(--border);
  background: var(--surface);
  overflow: hidden;
}

.pb-panel-left {
  border-radius: var(--radius) 0 0 var(--radius);
  border-right: 0;
}

.pb-panel-mid {
  border-right: 0;
}

.pb-panel-right {
  border-radius: 0 var(--radius) var(--radius) 0;
}

@media (max-width: 1280px) {
  .pb-content {
    grid-template-columns: minmax(270px, 300px) minmax(300px, 350px) 1fr;
  }
}

@media (max-width: 1080px) {
  .pb-content {
    grid-template-columns: minmax(260px, 300px) 1fr;
    grid-template-rows: minmax(300px, 48%) 1fr;
    gap: 10px;
  }

  .pb-panel-left,
  .pb-panel-mid,
  .pb-panel-right {
    border-radius: var(--radius);
    border-right: 1px solid var(--border);
  }

  .pb-panel-mid {
    grid-column: 2;
    grid-row: 1 / 3;
  }

  .pb-panel-right {
    grid-column: 1;
    grid-row: 2;
  }
}

@media (max-width: 720px) {
  .pb-content {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(260px, 40%) minmax(240px, 34%) minmax(200px, 26%);
    gap: 10px;
    padding: 4px 12px 14px;
  }

  .pb-panel-mid,
  .pb-panel-right {
    grid-column: 1;
  }

  .pb-panel-mid {
    grid-row: 2;
  }

  .pb-panel-right {
    grid-row: 3;
  }
}
</style>
