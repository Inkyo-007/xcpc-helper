import { describe, expect, it } from 'vitest'
import { buildDocument, type BuildInput } from './document'
import type {
  HeadingBlock,
  ImageBlock,
  MarkdownBlock,
  PageBreakBlock,
  PrintBookCover,
  PrintBookOptions,
  ResolvedTemplateInfo,
  TemplateBlock,
} from '@/types'

const COVER: PrintBookCover = { title: '测试册', subtitle: null, author: null, logo: null }

const OPTIONS: PrintBookOptions = {
  include_toc: true,
  include_meta: true,
  include_body: true,
  h1_page_break: true,
}

const INFO: ResolvedTemplateInfo = {
  name: '快速幂',
  cat: '数学',
  version_name: '快速幂',
  lang: 'cpp',
  file: 'qpow.cpp',
  code: 'int qpow() {}',
  body: '说明正文',
  tags: ['数论'],
  src: null,
  page: null,
  updated: '2026-07-05',
  priority: 5,
}

let idSeq = 0
const nid = (): string => `b${(idSeq += 1)}`

const heading = (title: string, level = 1): HeadingBlock => ({
  id: nid(),
  type: 'heading',
  title,
  heading_level: level,
})

const tpl = (
  overrides: Partial<TemplateBlock> = {},
  resolved: ResolvedTemplateInfo | null = INFO,
): TemplateBlock => ({
  id: nid(),
  type: 'template',
  template: '数学/快速幂',
  version: null,
  title: null,
  heading_level: 3,
  include_body: null,
  resolved,
  ...overrides,
})

const md = (content = '文字'): MarkdownBlock => ({
  id: nid(),
  type: 'markdown',
  title: null,
  content,
})

const img = (): ImageBlock => ({
  id: nid(),
  type: 'image',
  src: 'assets/a.png',
  caption: null,
  width: '80%',
})

const brk = (): PageBreakBlock => ({ id: nid(), type: 'page_break' })

function build(blocks: BuildInput['blocks'], options: Partial<PrintBookOptions> = {}) {
  return buildDocument({ cover: COVER, options: { ...OPTIONS, ...options }, blocks })
}

describe('buildDocument · 目录选项', () => {
  it('include_toc=true 生成目录条目，false 时不生成', () => {
    const on = build([heading('数学'), tpl()])
    expect(on.toc).toHaveLength(2)
    expect(on.toc?.[0]).toMatchObject({ title: '数学', level: 1, anchor: 'sec-01' })
    expect(on.toc?.[1]).toMatchObject({ title: '快速幂', level: 3, anchor: 'sec-02' })

    const off = build([heading('数学'), tpl()], { include_toc: false })
    expect(off.toc).toBeNull()
  })

  it('空册仍可导出：仅封面与空目录', () => {
    const doc = build([])
    expect(doc.sections).toHaveLength(0)
    expect(doc.toc).toEqual([])
    expect(doc.issues).toEqual([])
  })
})

describe('buildDocument · 元信息与说明选项', () => {
  it('include_meta=false 时模板节不带元信息', () => {
    const doc = build([tpl()], { include_meta: false })
    const sec = doc.sections[0]
    expect(sec.kind === 'template' && sec.meta).toBeNull()
  })

  it('include_body 三层优先级：块显式值 > 块 null 跟随册级', () => {
    // 块 null + 册 true → 有说明
    let doc = build([tpl()])
    let sec = doc.sections[0]
    expect(sec.kind === 'template' && sec.body).toBe('说明正文')

    // 块 null + 册 false → 无说明
    doc = build([tpl()], { include_body: false })
    sec = doc.sections[0]
    expect(sec.kind === 'template' && sec.body).toBeNull()

    // 块 true + 册 false → 有说明
    doc = build([tpl({ include_body: true })], { include_body: false })
    sec = doc.sections[0]
    expect(sec.kind === 'template' && sec.body).toBe('说明正文')

    // 块 false + 册 true → 无说明
    doc = build([tpl({ include_body: false })])
    sec = doc.sections[0]
    expect(sec.kind === 'template' && sec.body).toBeNull()

    // 说明正文为空 → 无说明
    doc = build([tpl({}, { ...INFO, body: '  ' })])
    sec = doc.sections[0]
    expect(sec.kind === 'template' && sec.body).toBeNull()
  })
})

describe('buildDocument · 分页边界', () => {
  it('首个章节总是另起一页（封面/目录边界）', () => {
    const doc = build([md()])
    expect(doc.sections[0].pageBreakBefore).toBe(true)
  })

  it('h1_page_break 开关只影响 h1，且不影响首页边界', () => {
    const blocks = [md(), heading('数学', 1), tpl({ heading_level: 2 })]
    const on = build(blocks)
    expect(on.sections[1].pageBreakBefore).toBe(true) // h1
    expect(on.sections[2].pageBreakBefore).toBe(false) // h2 模板节

    const off = build(blocks, { h1_page_break: false })
    expect(off.sections[1].pageBreakBefore).toBe(false)
  })

  it('相邻分页边界去重：page_break + h1 自动分页只保留一个', () => {
    const doc = build([md(), brk(), heading('数学', 1), md()])
    // heading 消费唯一分页符；其后 markdown 不再分页
    expect(doc.sections[1].pageBreakBefore).toBe(true)
    expect(doc.sections[2].pageBreakBefore).toBe(false)
  })

  it('连续 page_break 合并；尾部孤立分页符被丢弃', () => {
    const doc = build([md(), brk(), brk(), md(), brk()])
    expect(doc.sections.map((s) => s.pageBreakBefore)).toEqual([true, true])
    expect(doc.sections).toHaveLength(2)
  })

  it('失效模板被跳过时，待分页符顺延到下一节', () => {
    const doc = build([md(), brk(), tpl({}, null), md()])
    const kinds = doc.sections.map((s) => s.kind)
    expect(kinds).toEqual(['markdown', 'markdown'])
    expect(doc.sections[1].pageBreakBefore).toBe(true)
    expect(doc.issues[0]).toMatchObject({ level: 'error', blockIndex: 2 })
  })
})

describe('buildDocument · issues 与锚点', () => {
  it('失效模板：跳过该节、记 error、不占锚点', () => {
    const doc = build([tpl({}, null), tpl()])
    expect(doc.sections).toHaveLength(1)
    expect(doc.sections[0]).toMatchObject({ anchor: 'sec-01' })
    expect(doc.issues).toHaveLength(1)
    expect(doc.issues[0].level).toBe('error')
  })

  it('悬空 heading：记 warning（结尾或下一 heading 前无内容）', () => {
    const doc = build([heading('空章'), heading('数学'), tpl()])
    const warnings = doc.issues.filter((i) => i.level === 'warning')
    expect(warnings).toHaveLength(1)
    expect(warnings[0].message).toContain('空章')
  })

  it('锚点按章节顺序分配且与目录一致', () => {
    const doc = build([heading('数学'), tpl(), img(), heading('字符串', 2), md()])
    const anchors = doc.sections
      .filter((s) => s.kind === 'heading' || s.kind === 'template')
      .map((s) => s.anchor)
    expect(anchors).toEqual(['sec-01', 'sec-02', 'sec-03'])
    expect(doc.toc?.map((t) => t.anchor)).toEqual(['sec-01', 'sec-02', 'sec-03'])
    // markdown/image 不进目录
    expect(doc.toc).toHaveLength(3)
  })
})
