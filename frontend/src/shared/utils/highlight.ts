/**
 * 打印链路的静态代码高亮：highlight.js 整段高亮后按换行拆成独立行容器。
 * 跨行 span（多行注释/字符串）在行边界关闭并重开，保证着色不丢；
 * 行号直接烘焙进 HTML，分页克隆后依然连续，预览与打印天然一致。
 */

import hljs from 'highlight.js/lib/core'
import cpp from 'highlight.js/lib/languages/cpp'
import java from 'highlight.js/lib/languages/java'
import plaintext from 'highlight.js/lib/languages/plaintext'
import python from 'highlight.js/lib/languages/python'

hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('java', java)
hljs.registerLanguage('python', python)
hljs.registerLanguage('plaintext', plaintext)

const LANG_MAP: Record<string, string> = {
  c: 'cpp',
  'c++': 'cpp',
  cc: 'cpp',
  cxx: 'cpp',
  h: 'cpp',
  hpp: 'cpp',
  py: 'python',
  python3: 'python',
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

const TOKEN_RE = /<span class="[^"]*">|<\/span>|\n/g

/** 把 hljs 输出的 HTML 按 \n 拆行，跨行 span 在行尾补闭、行首重开。 */
export function splitHighlightedLines(html: string): string[] {
  const lines: string[] = []
  const open: string[] = []
  let current = ''
  let last = 0
  TOKEN_RE.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = TOKEN_RE.exec(html)) !== null) {
    current += html.slice(last, match.index)
    const token = match[0]
    if (token === '\n') {
      lines.push(current + '</span>'.repeat(open.length))
      current = open.join('')
    } else if (token === '</span>') {
      open.pop()
      current += token
    } else {
      open.push(token)
      current += token
    }
    last = TOKEN_RE.lastIndex
  }
  current += html.slice(last)
  lines.push(current)
  return lines
}

export interface HighlightedCode {
  /** 每行的着色 HTML（行内 span 平衡） */
  lines: string[]
  /** 带行号的完整容器 HTML */
  html: string
}

const CACHE_LIMIT = 120
const cache = new Map<string, HighlightedCode>()

/** 高亮一段代码并按行编号（行号烘焙进 HTML，跨页连续）。 */
export function highlightCode(code: string, lang: string): HighlightedCode {
  const normalized = code.replace(/\r\n?/g, '\n').replace(/\n+$/, '')
  const cacheKey = `${lang} ${normalized}`
  const hit = cache.get(cacheKey)
  if (hit) return hit

  const language = LANG_MAP[lang] ?? (hljs.getLanguage(lang) ? lang : 'plaintext')
  let value: string
  try {
    value = hljs.highlight(normalized, { language, ignoreIllegals: true }).value
  } catch {
    value = escapeHtml(normalized)
  }
  const lines = splitHighlightedLines(value)
  const body = lines
    .map((line, index) => {
      // 零宽空格保证空行也有正常行高
      const content = line || '​'
      return `<div class="pb-code-line"><span class="pb-code-ln">${index + 1}</span><span class="pb-code-tx">${content}</span></div>`
    })
    .join('')
  const result: HighlightedCode = {
    lines,
    html: `<pre class="pb-code"><code class="hljs language-${language}">${body}</code></pre>`,
  }
  if (cache.size >= CACHE_LIMIT) cache.clear()
  cache.set(cacheKey, result)
  return result
}
