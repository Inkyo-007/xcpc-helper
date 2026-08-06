/** 打印册原型状态（单例）：册列表、详情、块操作与级别偏好记忆。 */

import { computed, reactive, ref } from 'vue'
import { load, save } from '@/utils/storage'
import {
  MOCK_BOOKS,
  MOCK_TEMPLATE_DETAIL_MAP,
  MOCK_TEMPLATES,
  resolveTemplateInfo,
} from '@/mock/printbook'
import type {
  BookBlock,
  BookBlockType,
  HeadingBlock,
  ImageBlock,
  MarkdownBlock,
  PageBreakBlock,
  PrintBookCover,
  PrintBookDetail,
  PrintBookOptions,
  PrintBookSummary,
  TemplateBlock,
  TemplateSummary,
} from '@/types'

const HEADING_LEVEL_KEY = 'xc-pb-heading-level'
const TEMPLATE_LEVEL_KEY = 'xc-pb-template-level'

const books = ref<PrintBookSummary[]>([])
const detailMap = reactive<Record<string, PrintBookDetail>>({})
const activeName = ref<string | null>(null)
const templates = ref<TemplateSummary[]>(MOCK_TEMPLATES)

let idSeed = 0

function nextId(): string {
  idSeed += 1
  return `pb-${Date.now()}-${idSeed}`
}

function summaryOf(detail: PrintBookDetail): PrintBookSummary {
  return {
    name: detail.name,
    title: detail.cover.title,
    block_count: detail.blocks.length,
    updated: new Date().toISOString().slice(0, 10),
    error: null,
  }
}

for (const detail of MOCK_BOOKS) {
  detailMap[detail.name] = detail
  books.value.push(summaryOf(detail))
}
activeName.value = books.value[0]?.name ?? null

export function usePrintBooks() {
  const activeBook = computed(
    () => books.value.find((b) => b.name === activeName.value) ?? books.value[0] ?? null,
  )
  const activeDetail = computed(() =>
    activeBook.value ? detailMap[activeBook.value.name] : null,
  )

  const headingLevel = ref<number>(load<number>(HEADING_LEVEL_KEY, 2))
  const templateLevel = ref<number>(load<number>(TEMPLATE_LEVEL_KEY, 3))

  function rememberHeadingLevel(level: number): void {
    const value = Math.min(6, Math.max(1, Math.round(level)))
    headingLevel.value = value
    save(HEADING_LEVEL_KEY, value)
  }

  function rememberTemplateLevel(level: number): void {
    const value = Math.min(6, Math.max(1, Math.round(level)))
    templateLevel.value = value
    save(TEMPLATE_LEVEL_KEY, value)
  }

  function refreshSummary(name: string): void {
    const detail = detailMap[name]
    if (!detail) return
    const index = books.value.findIndex((b) => b.name === name)
    if (index >= 0) books.value[index] = summaryOf(detail)
  }

  function selectBook(name: string): void {
    if (detailMap[name]) activeName.value = name
  }

  function createBook(name: string, title: string): { ok: boolean; message?: string } {
    const clean = name.trim()
    if (!clean) return { ok: false, message: '册名不能为空' }
    if (detailMap[clean]) return { ok: false, message: `打印册「${clean}」已存在` }
    const detail: PrintBookDetail = {
      name: clean,
      cover: {
        title: title.trim() || clean,
        subtitle: null,
        author: null,
        logo: null,
      },
      options: {
        include_toc: true,
        include_meta: true,
        include_body: true,
        h1_page_break: true,
      },
      blocks: [],
    }
    detailMap[clean] = detail
    books.value.push(summaryOf(detail))
    activeName.value = clean
    return { ok: true }
  }

  function renameBook(name: string, newName: string, title: string): { ok: boolean; message?: string } {
    const detail = detailMap[name]
    if (!detail) return { ok: false, message: '打印册不存在' }
    const clean = newName.trim()
    if (!clean) return { ok: false, message: '册名不能为空' }
    if (clean !== name && detailMap[clean]) return { ok: false, message: `打印册「${clean}」已存在` }
    delete detailMap[name]
    detail.name = clean
    detail.cover.title = title.trim() || clean
    detailMap[clean] = detail
    const index = books.value.findIndex((b) => b.name === name)
    if (index >= 0) books.value[index] = summaryOf(detail)
    if (activeName.value === name) activeName.value = clean
    return { ok: true }
  }

  function deleteBook(name: string): void {
    delete detailMap[name]
    const index = books.value.findIndex((b) => b.name === name)
    if (index >= 0) books.value.splice(index, 1)
    if (activeName.value === name) {
      activeName.value = books.value[0]?.name ?? null
    }
  }

  function updateSettings(
    name: string,
    cover: PrintBookCover,
    options: PrintBookOptions,
  ): void {
    const detail = detailMap[name]
    if (!detail) return
    detail.cover = { ...cover }
    detail.options = { ...options }
    refreshSummary(name)
  }

  /** after=0 表示追加到末尾；N 表示插入到第 N 个条目之后。 */
  function insertIndex(after: number): number {
    const detail = activeDetail.value
    const length = detail?.blocks.length ?? 0
    if (after <= 0) return length
    return Math.min(after, length)
  }

  function addBlock(type: BookBlockType, after = 0): boolean {
    const detail = activeDetail.value
    if (!detail) return false
    let block: BookBlock
    if (type === 'heading') {
      block = { id: nextId(), type, title: '新章节', heading_level: headingLevel.value } satisfies HeadingBlock
    } else if (type === 'markdown') {
      block = { id: nextId(), type, title: null, content: '' } satisfies MarkdownBlock
    } else if (type === 'page_break') {
      block = { id: nextId(), type } satisfies PageBreakBlock
    } else {
      return false
    }
    detail.blocks.splice(insertIndex(after), 0, block)
    refreshSummary(detail.name)
    return true
  }

  function addImage(file: File, after = 0): boolean {
    const detail = activeDetail.value
    if (!detail) return false
    const block: ImageBlock = {
      id: nextId(),
      type: 'image',
      src: URL.createObjectURL(file),
      caption: file.name.replace(/\.[^.]+$/, ''),
      width: '80%',
    }
    detail.blocks.splice(insertIndex(after), 0, block)
    refreshSummary(detail.name)
    return true
  }

  function addTemplate(templateId: string, version: string | null, after = 0): boolean {
    const detail = activeDetail.value
    const resolved = resolveTemplateInfo(templateId, version)
    if (!detail || !resolved) return false
    const block: TemplateBlock = {
      id: nextId(),
      type: 'template',
      template: templateId,
      version,
      title: null,
      heading_level: templateLevel.value,
      include_body: null,
      resolved,
    }
    detail.blocks.splice(insertIndex(after), 0, block)
    refreshSummary(detail.name)
    return true
  }

  function updateBlock(block: BookBlock): void {
    const detail = activeDetail.value
    if (!detail) return
    const index = detail.blocks.findIndex((b) => b.id === block.id)
    if (index < 0) return
    if (block.type === 'template' && block.resolved === null) {
      block.resolved = resolveTemplateInfo(block.template, block.version)
    }
    detail.blocks[index] = block
    if (block.type === 'heading') rememberHeadingLevel(block.heading_level)
    if (block.type === 'template') rememberTemplateLevel(block.heading_level)
    refreshSummary(detail.name)
  }

  function removeBlock(id: string): void {
    const detail = activeDetail.value
    if (!detail) return
    const index = detail.blocks.findIndex((b) => b.id === id)
    if (index >= 0) detail.blocks.splice(index, 1)
    refreshSummary(detail.name)
  }

  function moveBlock(from: number, to: number): void {
    const detail = activeDetail.value
    if (!detail) return
    const blocks = [...detail.blocks]
    const target = to > from ? to - 1 : to
    const [item] = blocks.splice(from, 1)
    if (!item) return
    blocks.splice(Math.min(target, blocks.length), 0, item)
    detail.blocks = blocks
    refreshSummary(detail.name)
  }

  function templateDetail(id: string) {
    return MOCK_TEMPLATE_DETAIL_MAP[id] ?? null
  }

  return {
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
    templateDetail,
  }
}
