/** 模板库相关 API。 */

import { request } from '@/api/client'
import type {
  DiagnosticItem,
  SortMode,
  TemplateCreateInput,
  TemplateDetail,
  TemplateSummary,
} from '@/types'

export interface ApiCategory {
  id: string
  name: string
  count: number
}

export interface TemplateQuery {
  category?: string
  keyword?: string
  sort?: SortMode
}

export function fetchTemplates(query: TemplateQuery = {}): Promise<TemplateSummary[]> {
  const params = new URLSearchParams()
  if (query.category && query.category !== 'all') params.set('category', query.category)
  if (query.keyword?.trim()) params.set('keyword', query.keyword.trim())
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return request<TemplateSummary[]>(`/templates${qs ? `?${qs}` : ''}`)
}

export function fetchTemplateDetail(id: string): Promise<TemplateDetail> {
  const encoded = id.split('/').map(encodeURIComponent).join('/')
  return request<TemplateDetail>(`/templates/${encoded}`)
}

export function fetchCategories(): Promise<ApiCategory[]> {
  return request<ApiCategory[]>('/categories')
}

export function fetchDiagnostics(): Promise<{ items: DiagnosticItem[] }> {
  return request<{ items: DiagnosticItem[] }>('/diagnostics')
}

export function reloadTemplates(): Promise<{ templates: number; diagnostics: number }> {
  return request<{ templates: number; diagnostics: number }>('/templates/reload', {
    method: 'POST',
  })
}

/** 将 "分类/模板名" 形式的 id 编码为 URL 路径段 */
function encodeId(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/')
}

export function createTemplate(input: TemplateCreateInput): Promise<TemplateDetail> {
  return request<TemplateDetail>('/templates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteTemplate(id: string): Promise<void> {
  return request<void>(`/templates/${encodeId(id)}`, { method: 'DELETE' })
}
