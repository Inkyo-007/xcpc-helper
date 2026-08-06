import { describe, expect, it } from 'vitest'
import { highlightCode, splitHighlightedLines } from './highlight'

function countOccurrences(text: string, needle: string): number {
  return text.split(needle).length - 1
}

describe('splitHighlightedLines', () => {
  it('跨行 span 在行边界关闭并重开，每行标签平衡', () => {
    const html =
      '<span class="hljs-comment">/* first\nsecond\nthird */</span>\n<span class="hljs-keyword">int</span> x;'
    const lines = splitHighlightedLines(html)
    expect(lines).toHaveLength(4)
    for (const line of lines) {
      expect(countOccurrences(line, '<span')).toBe(countOccurrences(line, '</span>'))
    }
    expect(lines[0]).toContain('first')
    expect(lines[1]).toContain('<span class="hljs-comment">second')
    expect(lines[2]).toContain('third */</span>')
    expect(lines[3]).toContain('hljs-keyword')
  })

  it('无 span 的纯文本按行原样拆分', () => {
    expect(splitHighlightedLines('a\nb\nc')).toEqual(['a', 'b', 'c'])
  })
})

describe('highlightCode', () => {
  it('行号烘焙进 HTML 且从 1 连续编号', () => {
    const { html, lines } = highlightCode('int a;\nint b;\nint c;', 'cpp')
    expect(lines).toHaveLength(3)
    expect(html).toContain('<span class="pb-code-ln">1</span>')
    expect(html).toContain('<span class="pb-code-ln">2</span>')
    expect(html).toContain('<span class="pb-code-ln">3</span>')
  })

  it('行数守恒：含空行与多行注释的长代码', () => {
    const code = [
      '#include <bits/stdc++.h>',
      '',
      '/* 多行注释',
      '   第二行',
      '   第三行 */',
      'int main() {',
      '  return 0;',
      '}',
    ].join('\n')
    const { lines } = highlightCode(code, 'cpp')
    expect(lines).toHaveLength(8)
    // 原始拆行空行为空串；html 输出里空行补零宽空格保证行高
    expect(lines[1]).toBe('')
    expect(highlightCode(code, 'cpp').html).toContain('​')
  })

  it('去掉尾部换行，不产生多余空行', () => {
    const { lines } = highlightCode('int a;\n\n\n', 'cpp')
    expect(lines).toHaveLength(1)
  })

  it('未知语言回退 plaintext 且不抛错', () => {
    const { html } = highlightCode('hello <world>', 'not-a-lang')
    expect(html).toContain('language-plaintext')
    expect(html).toContain('&lt;world&gt;')
  })

  it('多行注释的着色跨行保留（span 平衡）', () => {
    const code = '/* a\nb\nc */\nint x;'
    const { lines } = highlightCode(code, 'cpp')
    expect(lines).toHaveLength(4)
    for (const line of lines) {
      expect(countOccurrences(line, '<span')).toBe(countOccurrences(line, '</span>'))
    }
    expect(lines[0]).toContain('hljs-comment')
    expect(lines[1]).toContain('hljs-comment')
  })
})
