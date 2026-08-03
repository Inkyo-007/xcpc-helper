/** 模板库数据 store（单例）：列表、分类、诊断与详情缓存，全部来自后端 API。 */

import { ref } from 'vue'
import {
  fetchCategories,
  fetchDiagnostics,
  fetchTemplateDetail,
  fetchTemplates,
  reloadTemplates,
  type TemplateQuery,
} from '@/api/template'
import type { Category, DiagnosticItem, TemplateDetail, TemplateSummary } from '@/types'

/** 分类色板：按后端返回顺序循环取色，保持视觉区分度 */
const HUE_PALETTE = [160, 25, 280, 200, 340, 80, 120, 300, 0, 220]

const templates = ref<TemplateSummary[]>([])
const categories = ref<Category[]>([{ id: 'all', name: '全部', hue: null }])
const diagnostics = ref<DiagnosticItem[]>([])
const listLoading = ref(false)
const listError = ref<string | null>(null)
const initialized = ref(false)

const detailCache = new Map<string, TemplateDetail>()
let currentQuery: TemplateQuery = { sort: 'updated' }

async function loadList(query?: TemplateQuery): Promise<void> {
  if (query) currentQuery = query
  listLoading.value = true
  listError.value = null
  try {
    templates.value = await fetchTemplates(currentQuery)
  } catch (err) {
    listError.value = err instanceof Error ? err.message : '模板列表加载失败'
  } finally {
    listLoading.value = false
  }
}

async function loadCategories(): Promise<void> {
  try {
    const list = await fetchCategories()
    categories.value = [
      { id: 'all', name: '全部', hue: null },
      ...list.map((c, index) => ({
        id: c.id,
        name: c.name,
        count: c.count,
        hue: HUE_PALETTE[index % HUE_PALETTE.length],
      })),
    ]
  } catch {
    // 分类加载失败时保留"全部"，列表仍可用
  }
}

async function loadDiagnostics(): Promise<void> {
  try {
    diagnostics.value = (await fetchDiagnostics()).items
  } catch {
    diagnostics.value = []
  }
}

async function init(): Promise<void> {
  await Promise.all([loadList(), loadCategories(), loadDiagnostics()])
  initialized.value = true
}

async function loadDetail(id: string): Promise<TemplateDetail | null> {
  const cached = detailCache.get(id)
  if (cached) return cached
  try {
    const detail = await fetchTemplateDetail(id)
    detailCache.set(id, detail)
    return detail
  } catch {
    return null
  }
}

/** 触发后端重建索引并刷新全部前端状态（content/ 变更后调用） */
async function reload(): Promise<void> {
  detailCache.clear()
  await reloadTemplates()
  await init()
}

function categoryHue(id: string): number {
  return categories.value.find((c) => c.id === id)?.hue ?? 160
}

function categoryName(id: string): string {
  return categories.value.find((c) => c.id === id)?.name ?? id
}

export function useTemplates() {
  return {
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
    categoryHue,
    categoryName,
  }
}
