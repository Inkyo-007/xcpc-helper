<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import DeleteConfirmModal from '@/shared/components/DeleteConfirmModal.vue'
import BookNameModal from '@/features/printbook/components/BookNameModal.vue'
import BookSettingsModal from '@/features/printbook/components/BookSettingsModal.vue'
import BookSidePanel from '@/features/printbook/components/BookSidePanel.vue'
import EntryEditorModal from '@/features/printbook/components/EntryEditorModal.vue'
import EntryList from '@/features/printbook/components/EntryList.vue'
import BookPreview from '@/features/printbook/components/preview/BookPreview.vue'
import { usePrintBooks } from '@/features/printbook/store'
import BookTransferModal from '@/features/transfer/components/BookTransferModal.vue'
import type {
  BookBlock,
  BookBlockType,
  PrintBookCover,
  PrintBookOptions,
  PrintBookSummary,
} from '@/features/printbook/types'

const message = useMessage()
const {
  books,
  templates,
  allTemplates,
  details,
  activeBook,
  activeDetail,
  headingLevel,
  templateLevel,
  rememberHeadingLevel,
  rememberTemplateLevel,
  init,
  selectBook,
  refreshBooks,
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
  pickerQuery,
  ensureTemplateDetail,
} = usePrintBooks()

onMounted(async () => {
  const result = await init()
  if (!result.ok) message.error(result.message ?? '打印册加载失败')
})

const showBookName = ref(false)
const bookNameMode = ref<'create' | 'rename'>('create')
const showSettings = ref(false)
const showTransfer = ref(false)
const editingBlock = ref<BookBlock | null>(null)
const deletingBook = ref<PrintBookSummary | null>(null)

const blockCount = computed(() => activeDetail.value?.blocks.length ?? 0)
const blocks = computed(() => activeDetail.value?.blocks ?? [])

function report(result: { ok: boolean; message?: string }): void {
  if (!result.ok) message.error(result.message ?? '操作失败')
}

async function onAddBlock(type: BookBlockType, after: number): Promise<void> {
  report(await addBlock(type, after))
}

async function onAddImage(file: File, after: number): Promise<void> {
  report(await addImage(file, after))
}

async function onAddTemplate(
  templateId: string,
  version: string | null,
  after: number,
): Promise<void> {
  report(await addTemplate(templateId, version, after))
}

async function onSaveBlock(block: BookBlock, imageFile?: File): Promise<void> {
  report(await updateBlock(block, imageFile))
}

async function onRemoveBlock(id: string): Promise<void> {
  report(await removeBlock(id))
}

async function onMoveBlock(from: number, to: number): Promise<void> {
  report(await moveBlock(from, to))
}

async function onSelectBook(name: string): Promise<void> {
  report(await selectBook(name))
}

async function onBooksImported(names: string[]): Promise<void> {
  report(await refreshBooks(names[0]))
}

async function onBookCreated(name: string, title: string): Promise<void> {
  const result = await createBook(name, title)
  if (result.ok) {
    message.success(`已创建打印册「${name}」`)
  } else {
    message.error(result.message ?? '创建失败')
  }
}

async function onBookRenamed(name: string): Promise<void> {
  const book = activeBook.value
  if (!book) return
  const result = await renameBook(book.name, name)
  if (result.ok) {
    message.success(`已重命名为「${name}」`)
  } else {
    message.error(result.message ?? '重命名失败')
  }
}

async function onSettingsSaved(
  cover: PrintBookCover,
  options: PrintBookOptions,
  headingLevelValue: number,
  templateLevelValue: number,
): Promise<void> {
  const book = activeBook.value
  if (!book) return
  const result = await updateSettings(book.name, cover, options)
  if (result.ok) {
    rememberHeadingLevel(headingLevelValue)
    rememberTemplateLevel(templateLevelValue)
    message.success('已保存封面与选项')
  } else {
    message.error(result.message ?? '保存失败')
  }
}

async function confirmDeleteBook(): Promise<void> {
  const book = deletingBook.value
  if (!book) return
  const result = await deleteBook(book.name)
  if (result.ok) {
    message.success(`已删除打印册「${book.title || book.name}」`)
    deletingBook.value = null
  } else {
    message.error(result.message ?? '删除失败')
  }
}
</script>

<template>
  <div class="pb-page">
    <div class="pb-content">
      <BookSidePanel
        class="pb-panel pb-panel-left"
        :books="books"
        :templates="templates"
        :all-templates="allTemplates"
        :details="details"
        :active-name="activeBook?.name ?? null"
        :block-count="blockCount"
        @select-book="onSelectBook"
        @new-book="bookNameMode = 'create'; showBookName = true"
        @transfer="showTransfer = true"
        @settings="showSettings = true"
        @rename="bookNameMode = 'rename'; showBookName = true"
        @delete-book="deletingBook = activeBook"
        @add-block="onAddBlock"
        @add-image="onAddImage"
        @add-template="onAddTemplate"
        @picker-query="pickerQuery"
        @request-detail="ensureTemplateDetail"
      />

      <EntryList
        class="pb-panel pb-panel-mid"
        :blocks="blocks"
        @edit="editingBlock = $event"
        @delete="onRemoveBlock"
        @move="onMoveBlock"
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
    <BookTransferModal
      v-model:show="showTransfer"
      :active-name="activeBook?.name ?? null"
      @imported="onBooksImported"
    />
  </div>
</template>

<style scoped>
.pb-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
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
