/** marked 的 KaTeX 扩展：$...$ 行内公式与 $$...$$ 展示公式。 */

import katex, { type KatexOptions } from 'katex'
import type { MarkedExtension, Tokens } from 'marked'

// 边界规则对齐 cmark-gfm，且对界符两侧的 CJK 文本与全角标点不设限制：
// - 开界符后不能是空白，闭界符前不能是空白；
// - 单个 $ 的闭界符后不能紧跟数字，避免「$5 和 $10」这类金额被误解析；
// - 行内公式内容不含 $ 与换行，避免跨公式、跨行误合并。
const INLINE_RULE = /^\$(?!\$)(?=\S)((?:\\.|[^\\$\n])+?)(?<=\S)\$(?!\d)/
const INLINE_DISPLAY_RULE = /^\$\$(?!\$)(?=\S)((?:\\.|[^\\\n])+?)(?<=\S)\$\$/
const BLOCK_RULE = /^(\${1,2})\n((?:\\[\s\S]|[^\\])+?)\n\1(?:\n|$)/

interface KatexToken extends Tokens.Generic {
  text: string
  displayMode: boolean
}

function render(token: KatexToken, options: KatexOptions): string {
  return katex.renderToString(token.text, { ...options, displayMode: token.displayMode })
}

/** $ 前紧邻奇数个反斜杠视为被转义。 */
function isEscaped(src: string, index: number): boolean {
  let backslashes = 0
  let i = index - 1
  while (i >= 0 && src[i] === '\\') {
    backslashes += 1
    i -= 1
  }
  return backslashes % 2 === 1
}

function isInlineMath(src: string, index: number): boolean {
  const rest = src.slice(index)
  return INLINE_DISPLAY_RULE.test(rest) || INLINE_RULE.test(rest)
}

/**
 * marked 消费普通文本前调用 start 定位下一个公式起点（src 已截去当前首字符）。
 * index 0 处的 $ 不可能被转义：转义序列已被内置 escape 分词器优先消费。
 */
function findInlineStart(src: string): number | undefined {
  let from = 0
  for (;;) {
    const index = src.indexOf('$', from)
    if (index === -1) return undefined
    if (!isEscaped(src, index) && isInlineMath(src, index)) return index
    from = index + 1
  }
}

export default function markedKatex(options: KatexOptions = {}): MarkedExtension {
  return {
    extensions: [
      {
        name: 'inlineKatex',
        level: 'inline',
        start: findInlineStart,
        tokenizer(src) {
          const match = INLINE_DISPLAY_RULE.exec(src) ?? INLINE_RULE.exec(src)
          if (!match) return undefined
          const token: KatexToken = {
            type: 'inlineKatex',
            raw: match[0],
            text: match[1].trim(),
            displayMode: match[0].startsWith('$$'),
          }
          return token
        },
        renderer(token) {
          return render(token as KatexToken, options)
        },
      },
      {
        name: 'blockKatex',
        level: 'block',
        tokenizer(src) {
          const match = BLOCK_RULE.exec(src)
          if (!match) return undefined
          const token: KatexToken = {
            type: 'blockKatex',
            raw: match[0],
            text: match[2].trim(),
            displayMode: match[1].length === 2,
          }
          return token
        },
        renderer(token) {
          return render(token as KatexToken, options) + '\n'
        },
      },
    ],
  }
}
