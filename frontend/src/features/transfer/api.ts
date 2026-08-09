/** 导入/导出相关 API。 */

import { ApiError, request, toApiError } from '@/shared/api/client'
import { extractFilename } from '@/features/transfer/model/download'
import type {
  BookAnalyzeResult,
  ConflictStrategy,
  ImportReport,
  TemplateAnalyzeResult,
} from '@/features/transfer/types'

/** 先 fetch 校验响应再落地 blob：裸 <a href> 在后端报错时会把 JSON 错误体存成文件。 */
async function download(path: string, fallbackName: string): Promise<void> {
  let resp: Response
  try {
    resp = await fetch(`/api/transfer${path}`)
  } catch {
    throw new ApiError(0, 'network_error', '无法连接后端服务，请确认后端已启动')
  }
  if (!resp.ok) {
    throw await toApiError(resp, `导出失败（${resp.status}）`)
  }
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = extractFilename(resp.headers.get('Content-Disposition'), fallbackName)
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

export function downloadTemplatesArchive(): Promise<void> {
  return download('/export/templates', 'xcpc-templates.zip')
}

export function downloadAllBooksArchive(): Promise<void> {
  return download('/export/books', 'xcpc-books.zip')
}

export function downloadBookArchive(name: string): Promise<void> {
  return download(`/export/books/${encodeURIComponent(name)}`, `xcpc-book-${name}.zip`)
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
