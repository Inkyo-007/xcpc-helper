/** 打印册相关 API。 */

import { request } from '@/api/client'
import type {
  BookBlock,
  PrintBookCover,
  PrintBookDetail,
  PrintBookOptions,
  PrintBookSummary,
} from '@/types'

export interface PrintBookUpdatePayload {
  cover?: PrintBookCover
  options?: PrintBookOptions
  new_name?: string
}

export function fetchBooks(): Promise<PrintBookSummary[]> {
  return request<PrintBookSummary[]>('/print-books')
}

export function fetchBook(name: string): Promise<PrintBookDetail> {
  return request<PrintBookDetail>(`/print-books/${encodeURIComponent(name)}`)
}

export function createBook(name: string, title?: string): Promise<PrintBookDetail> {
  return request<PrintBookDetail>('/print-books', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, title: title ?? null }),
  })
}

export function updateBook(
  name: string,
  payload: PrintBookUpdatePayload,
): Promise<PrintBookDetail> {
  return request<PrintBookDetail>(`/print-books/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteBook(name: string): Promise<void> {
  return request<void>(`/print-books/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

/** 全量替换块列表，后端返回重新解析后的完整详情 */
export function replaceBlocks(name: string, blocks: BookBlock[]): Promise<PrintBookDetail> {
  return request<PrintBookDetail>(`/print-books/${encodeURIComponent(name)}/blocks`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ blocks }),
  })
}

/** 上传图片资源，返回可直接渲染的资源 URL */
export function uploadAsset(name: string, file: File): Promise<{ src: string }> {
  const form = new FormData()
  form.append('file', file)
  return request<{ src: string }>(`/print-books/${encodeURIComponent(name)}/assets`, {
    method: 'POST',
    body: form,
  })
}
