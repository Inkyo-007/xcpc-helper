/** 导入/导出相关 API。 */

import { request } from '@/shared/api/client'
import type {
  BookAnalyzeResult,
  ConflictStrategy,
  ImportReport,
  TemplateAnalyzeResult,
} from '@/features/transfer/types'

/** 触发浏览器下载（导出端点为普通 GET，直连即可，无需经过 request 封装） */
function download(path: string): void {
  const a = document.createElement('a')
  a.href = `/api/transfer${path}`
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

export function downloadTemplatesArchive(): void {
  download('/export/templates')
}

export function downloadAllBooksArchive(): void {
  download('/export/books')
}

export function downloadBookArchive(name: string): void {
  download(`/export/books/${encodeURIComponent(name)}`)
}

function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  return request<T>(`/transfer${path}`, { method: 'POST', body: form })
}

export function analyzeTemplatesArchive(file: File): Promise<TemplateAnalyzeResult> {
  return upload('/import/templates/analyze', file)
}

export function applyTemplatesImport(
  stagingId: string,
  strategy: ConflictStrategy,
): Promise<ImportReport> {
  return request<ImportReport>('/transfer/import/templates/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ staging_id: stagingId, strategy }),
  })
}

export function analyzeBooksArchive(file: File): Promise<BookAnalyzeResult> {
  return upload('/import/books/analyze', file)
}

export function applyBooksImport(
  stagingId: string,
  strategy: ConflictStrategy,
): Promise<ImportReport> {
  return request<ImportReport>('/transfer/import/books/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ staging_id: stagingId, strategy }),
  })
}
