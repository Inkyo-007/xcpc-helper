import { Marked } from 'marked'
import { describe, expect, it } from 'vitest'
import markedKatex from './marked-katex'

const marked = new Marked()
marked.use(markedKatex({ throwOnError: false }))

const parse = (src: string): string => marked.parse(src, { async: false })
const KATEX = 'class="katex"'

describe('markedKatex', () => {
  it('解析行内公式', () => {
    expect(parse('公式 $x+1$ 结束')).toContain(KATEX)
  })

  it('解析块级公式', () => {
    expect(parse('$$\n\\frac{a}{b}\n$$')).toContain('katex-display')
  })

  it('解析行内展示公式', () => {
    expect(parse('前 $$x+y$$ 后')).toContain('katex-display')
  })

  it('开界符前允许全角标点（无空格）', () => {
    const html = parse('这里有一个公式：$x+1$，它没有正常显示。')
    expect(html).toContain(KATEX)
    expect(html).not.toContain('$x+1$')
  })

  it('闭界符后允许直接衔接 CJK 字符', () => {
    expect(parse('公式 $x$渲染正常')).toContain(KATEX)
  })

  it('换行后的行首公式', () => {
    expect(parse('上文\n$x+1$ 在行首')).toContain(KATEX)
  })

  it('同段多个公式紧邻 CJK 文本均可解析', () => {
    const src = '像这样：$1234567891011121314151617181920$ 渲染 $123$。'
    const html = parse(src)
    expect(html.match(/class="katex"/g)).toHaveLength(2)
  })

  it('复现打印册中的长公式', () => {
    const src =
      '这里有一个公式：$f_{i,j,k} \\gets (f_{i+1,j+b_i,k | 1} + a_i) \\times \\frac{p_i}{100} + (f_{i+1,j+b_i,k | 2} + a_i) \\times (1 - \\frac{p_i}{100})$，它没有正常显示。'
    const html = parse(src)
    expect(html).toContain(KATEX)
    expect(html).not.toContain('$f_{i,j,k}')
  })

  it('金额不被误解析', () => {
    expect(parse('价格 $5 和 $10 元')).not.toContain(KATEX)
  })

  it('闭界符后紧跟数字不解析', () => {
    expect(parse('共 $x$2 种')).not.toContain(KATEX)
  })

  it('开界符后是空白不解析', () => {
    expect(parse('算式 $ x$')).not.toContain(KATEX)
  })

  it('闭界符前是空白不解析', () => {
    expect(parse('算式 $x $')).not.toContain(KATEX)
  })

  it('未闭合的 $ 原样输出', () => {
    expect(parse('只有一边 $x')).not.toContain(KATEX)
  })

  it('转义的 \\$ 不解析', () => {
    const html = parse('价格 \\$5 和 \\$10')
    expect(html).not.toContain(KATEX)
    expect(html).toContain('$5')
  })

  it('行间公式不被行内规则截断', () => {
    const html = parse('前 $$x$y$$ 后')
    // 整个 $$...$$ 作为一个 token 被消费（KaTeX 拒绝内容中的 $ 属预期行为）
    expect(html).toContain('katex')
    expect(html).not.toContain('$$')
  })
})
