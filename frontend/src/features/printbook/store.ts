/** 打印册数据 store（单例）：册列表、详情缓存与块操作，全部来自后端 API。
 *
 * 数据流约定：
 * - 册级操作（建册/改名/删除/封面选项）直接调用 API，成功后刷新列表；
 * - 块操作先在本地 detail 上即时变更（预览实时响应），随后整体 PUT /blocks
 *   持久化，成功后以后端返回的详情（重新解析的 resolved）覆盖本地；
 *   失败时重拉详情回滚本地改动；
 * - 模板选择器的搜索/排序由后端完成（fetchTemplates），展开版本时按需
 *   拉取模板详情缓存到 details。
 */

import { computed, reactive, ref } from 'vue'
import {
  createBook as apiCreateBook,
  deleteBook as apiDeleteBook,
  fetchBook,
  fetchBooks,
  replaceBlocks,
  updateBook as apiUpdateBook,
  uploadAsset,
} from '@/features/printbook/api'
import { fetchTemplateDetail, fetchTemplates, type TemplateQuery } from '@/features/template/api'
import { load, save } from '@/shared/utils/storage'
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
  ResolvedTemplateInfo,
  TemplateBlock,
} from '@/features/printbook/types'
import type { TemplateDetail, TemplateSummary } from '@/features/template/types'

const HEADING_LEVEL_KEY = 'xc-pb-heading-level'
const TEMPLATE_LEVEL_KEY = 'xc-pb-template-level'

interface OpResult {
  ok: boolean
  message?: string
}

const books = ref<PrintBookSummary[]>([])
const detailMap = reactive<Record<string, PrintBookDetail>>({})
const activeName = ref<string | null>(null)
/** 模板选择器当前查询结果（服务端搜索/排序） */
const templates = ref<TemplateSummary[]>([])
/** 全量模板摘要：用于选择器分类计数 */
const allTemplates = ref<TemplateSummary[]>([])
/** 已拉取的模板详情缓存（版本展开、template 块本地解析用） */
const details = reactive<Record<string, TemplateDetail>>({})
const initialized = ref(false)

let idSeed = 0

function nextId(): string {
  idSeed += 1
  return `pb-${Date.now()}-${idSeed}`
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

/** 本地即时解析：与服务端 document 的版本语义保持一致
 * （null=主版本，"~"=顶层单版本，其余按副标签名匹配）。 */
function resolveLocal(templateId: string, version: string | null): ResolvedTemplateInfo | null {
  const detail = details[templateId]
  if (!detail || !detail.variants.length) return null
  const target =
    version === null
      ? detail.variants[0]
      : detail.variants.find((v) =>
          version === '~' ? v.id === templateId : v.name === version || v.id === templateId,
        )
  if (!target) return null
  return {
    name: detail.name,
    cat: detail.cat,
    version_name: target.name,
    lang: target.lang,
    file: target.file,
    code: target.code,
    body: target.body,
    tags: target.tags,
    src: target.src,
    page: target.page,
    updated: target.updated,
    priority: target.priority,
  }
}

function patchSummary(name: string): void {
  const detail = detailMap[name]
  const index = books.value.findIndex((b) => b.name === name)
  if (!detail || index < 0) return
  books.value[index] = {
    name: detail.name,
    title: detail.cover.title || detail.name,
    block_count: detail.blocks.length,
    updated: new Date().toISOString(),
    error: null,
  }
}

async function refreshList(): Promise<void> {
  books.value = await fetchBooks()
}

async function loadDetail(name: string): Promise<PrintBookDetail> {
  const detail = await fetchBook(name)
  detailMap[name] = detail
  return detail
}

// ===== 初始化与选择 =====

async function init(): Promise<OpResult> {
  try {
    const [list, all] = await Promise.all([fetchBooks(), fetchTemplates({ sort: 'updated' })])
    books.value = list
    allTemplates.value = all
    templates.value = all
    const first = list.find((b) => !b.error)?.name ?? null
    if (first) await loadDetail(first)
    activeName.value = first
    initialized.value = true
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, '打印册加载失败') }
  }
}

async function selectBook(name: string): Promise<OpResult> {
  try {
    await loadDetail(name)
    activeName.value = name
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, '打印册读取失败') }
  }
}

/** 册导入等外部变更后刷新列表并选中指定册（缺省选中第一本可用册） */
async function refreshBooks(selectName?: string): Promise<OpResult> {
  try {
    await refreshList()
    const target =
      selectName && books.value.some((b) => b.name === selectName)
        ? selectName
        : (books.value.find((b) => !b.error)?.name ?? null)
    if (target) await loadDetail(target)
    activeName.value = target
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, '打印册加载失败') }
  }
}

// ===== 册级操作 =====

async function createBook(name: string, title: string): Promise<OpResult> {
  const clean = name.trim()
  if (!clean) return { ok: false, message: '册名不能为空' }
  try {
    const detail = await apiCreateBook(clean, title.trim() || undefined)
    detailMap[detail.name] = detail
    await refreshList()
    activeName.value = detail.name
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, '创建失败') }
  }
}

/** 仅改册名；封面标题由"封面与选项"（updateSettings）独立维护 */
async function renameBook(name: string, newName: string): Promise<OpResult> {
  const clean = newName.trim()
  if (!clean) return { ok: false, message: '册名不能为空' }
  try {
    const detail = await apiUpdateBook(name, { new_name: clean })
    delete detailMap[name]
    detailMap[detail.name] = detail
    await refreshList()
    if (activeName.value === name) activeName.value = detail.name
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, '重命名失败') }
  }
}

async function deleteBook(name: string): Promise<OpResult> {
  try {
    await apiDeleteBook(name)
    delete detailMap[name]
    await refreshList()
    if (activeName.value === name) {
      const first = books.value.find((b) => !b.error)?.name ?? null
      if (first) await loadDetail(first)
      activeName.value = first
    }
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, '删除失败') }
  }
}

async function updateSettings(
  name: string,
  cover: PrintBookCover,
  options: PrintBookOptions,
): Promise<OpResult> {
  try {
    const detail = await apiUpdateBook(name, { cover, options })
    detailMap[detail.name] = detail
    await refreshList()
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, '保存失败') }
  }
}

// ===== 块操作 =====

/** 本地改动整体提交；失败时重拉详情回滚，保证本地与磁盘一致 */
async function persistBlocks(): Promise<void> {
  const detail = activeDetail.value
  if (!detail) return
  try {
    const fresh = await replaceBlocks(detail.name, detail.blocks)
    detailMap[fresh.name] = fresh
    patchSummary(fresh.name)
  } catch (err) {
    await loadDetail(detail.name).catch(() => undefined)
    throw err
  }
}

async function commitBlocks(fallback: string): Promise<OpResult> {
  try {
    await persistBlocks()
    return { ok: true }
  } catch (err) {
    return { ok: false, message: errorMessage(err, fallback) }
  }
}

/** after=-1 表示追加到末尾；0 表示插入到头部；N 表示插入到第 N 个条目之后。 */
function insertIndex(after: number): number {
  const detail = activeDetail.value
  const length = detail?.blocks.length ?? 0
  if (after < 0) return length
  return Math.min(after, length)
}

async function addBlock(type: BookBlockType, after = -1): Promise<OpResult> {
  const detail = activeDetail.value
  if (!detail) return { ok: false, message: '请先选择打印册' }
  let block: BookBlock
  if (type === 'heading') {
    block = {
      id: nextId(),
      type,
      title: '新章节',
      heading_level: headingLevel.value,
    } satisfies HeadingBlock
  } else if (type === 'markdown') {
    block = { id: nextId(), type, title: null, content: '' } satisfies MarkdownBlock
  } else if (type === 'page_break') {
    block = { id: nextId(), type } satisfies PageBreakBlock
  } else {
    return { ok: false, message: '该类型需要通过列表添加' }
  }
  detail.blocks.splice(insertIndex(after), 0, block)
  patchSummary(detail.name)
  return commitBlocks('添加失败')
}

async function addImage(file: File, after = -1): Promise<OpResult> {
  const detail = activeDetail.value
  if (!detail) return { ok: false, message: '请先选择打印册' }
  try {
    const { src } = await uploadAsset(detail.name, file)
    const block: ImageBlock = {
      id: nextId(),
      type: 'image',
      src,
      caption: file.name.replace(/\.[^.]+$/, ''),
      width: '80%',
    }
    detail.blocks.splice(insertIndex(after), 0, block)
    patchSummary(detail.name)
  } catch (err) {
    return { ok: false, message: errorMessage(err, '图片上传失败') }
  }
  return commitBlocks('添加失败')
}

async function addTemplate(
  templateId: string,
  version: string | null,
  after = -1,
): Promise<OpResult> {
  const detail = activeDetail.value
  if (!detail) return { ok: false, message: '请先选择打印册' }
  await ensureTemplateDetail(templateId)
  const block: TemplateBlock = {
    id: nextId(),
    type: 'template',
    template: templateId,
    version,
    title: null,
    heading_level: templateLevel.value,
    include_body: null,
    // 先用本地缓存即时渲染，持久化后由后端重新解析覆盖
    resolved: resolveLocal(templateId, version),
  }
  detail.blocks.splice(insertIndex(after), 0, block)
  patchSummary(detail.name)
  return commitBlocks('添加失败')
}

async function updateBlock(block: BookBlock, imageFile?: File): Promise<OpResult> {
  const detail = activeDetail.value
  if (!detail) return { ok: false, message: '打印册不存在' }
  const index = detail.blocks.findIndex((b) => b.id === block.id)
  if (index < 0) return { ok: false, message: '条目不存在' }
  if (block.type === 'image' && imageFile) {
    try {
      const { src } = await uploadAsset(detail.name, imageFile)
      block.src = src
    } catch (err) {
      return { ok: false, message: errorMessage(err, '图片上传失败') }
    }
  }
  if (block.type === 'template') {
    await ensureTemplateDetail(block.template)
    if (block.resolved === null) block.resolved = resolveLocal(block.template, block.version)
  }
  detail.blocks[index] = block
  if (block.type === 'heading') rememberHeadingLevel(block.heading_level)
  if (block.type === 'template') rememberTemplateLevel(block.heading_level)
  patchSummary(detail.name)
  return commitBlocks('保存失败')
}

async function removeBlock(id: string): Promise<OpResult> {
  const detail = activeDetail.value
  if (!detail) return { ok: false, message: '打印册不存在' }
  const index = detail.blocks.findIndex((b) => b.id === id)
  if (index < 0) return { ok: false, message: '条目不存在' }
  detail.blocks.splice(index, 1)
  patchSummary(detail.name)
  return commitBlocks('删除失败')
}

async function moveBlock(from: number, to: number): Promise<OpResult> {
  const detail = activeDetail.value
  if (!detail) return { ok: false, message: '打印册不存在' }
  const blocks = [...detail.blocks]
  const target = to > from ? to - 1 : to
  const [item] = blocks.splice(from, 1)
  if (!item) return { ok: false, message: '条目不存在' }
  blocks.splice(Math.min(target, blocks.length), 0, item)
  detail.blocks = blocks
  return commitBlocks('排序保存失败')
}

// ===== 模板选择器数据 =====

/** 服务端搜索/排序（选择器 200ms 防抖后调用） */
async function pickerQuery(query: TemplateQuery): Promise<void> {
  try {
    templates.value = await fetchTemplates(query)
  } catch {
    // 查询失败保留当前列表，不打扰编辑
  }
}

/** 按需拉取模板详情（展开版本列表、template 块本地解析用） */
async function ensureTemplateDetail(id: string): Promise<void> {
  if (details[id]) return
  try {
    details[id] = await fetchTemplateDetail(id)
  } catch {
    // 拉取失败时块 resolved 由后端解析兜底
  }
}

// ===== 级别偏好记忆 =====

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

const activeBook = computed(
  () => books.value.find((b) => b.name === activeName.value) ?? null,
)
const activeDetail = computed(() =>
  activeName.value ? (detailMap[activeName.value] ?? null) : null,
)

export function usePrintBooks() {
  return {
    books,
    templates,
    allTemplates,
    details,
    activeBook,
    activeDetail,
    initialized,
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
  }
}
