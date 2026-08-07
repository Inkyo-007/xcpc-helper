/** 共享 Markdown 渲染（marked + KaTeX），模板详情与打印册预览同源。 */

import { Marked } from 'marked'
import markedKatex from 'marked-katex-extension'
import 'katex/dist/katex.min.css'

// 支持 $...$ 行内公式与 $$...$$ 块级公式（KaTeX）
const marked = new Marked()
marked.use(markedKatex({ throwOnError: false }))

export function renderMarkdown(content: string): string {
  // 本地内容可信，直接渲染；无异步扩展时 parse 同步返回字符串
  return marked.parse(content, { async: false })
}

const CACHE_LIMIT = 200
const cache = new Map<string, string>()

/** 按内容缓存渲染结果，避免预览重排时重复解析。 */
export function renderMarkdownCached(content: string): string {
  const hit = cache.get(content)
  if (hit !== undefined) return hit
  const html = renderMarkdown(content)
  if (cache.size >= CACHE_LIMIT) cache.clear()
  cache.set(content, html)
  return html
}
