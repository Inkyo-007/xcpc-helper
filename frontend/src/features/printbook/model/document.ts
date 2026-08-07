/**
 * 打印册文档模型层：buildDocument 是唯一消费 options 的纯函数。
 * 块 + 选项 → 纯数据结构（封面、目录、有序章节、issues），
 * 屏幕预览与打印导出共用同一份输出，保证二者一致。
 */

import type {
  PrintBookCover,
  PrintBookOptions,
  ResolvedTemplateInfo,
  BookBlock,
} from '@/features/printbook/types'

export type IssueLevel = 'error' | 'warning'

export interface BookIssue {
  /** 在块列表中的下标，便于前端定位 */
  blockIndex: number
  level: IssueLevel
  message: string
}

export interface TocEntry {
  anchor: string
  title: string
  level: number
}

export interface DocMeta {
  cat: string
  versionName: string
  file: string
  lang: string
  tags: string[]
  src: string | null
  page: string | null
  updated: string | null
  priority: number
}

interface SectionBase {
  /** 稳定的渲染 key（取块 id） */
  key: string
  pageBreakBefore: boolean
}

export interface HeadingSection extends SectionBase {
  kind: 'heading'
  anchor: string
  title: string
  level: number
}

export interface TemplateSection extends SectionBase {
  kind: 'template'
  anchor: string
  title: string
  level: number
  meta: DocMeta | null
  info: ResolvedTemplateInfo
  /** 已按 include_body 三层优先级解析后的说明正文；null=不显示说明框 */
  body: string | null
}

export interface MarkdownSection extends SectionBase {
  kind: 'markdown'
  title: string | null
  content: string
}

export interface ImageSection extends SectionBase {
  kind: 'image'
  src: string
  caption: string | null
  width: string
}

export type DocSection = HeadingSection | TemplateSection | MarkdownSection | ImageSection

export interface BookDocument {
  coverTitle: string
  subtitle: string | null
  author: string | null
  logo: string | null
  /** null=不生成目录 */
  toc: TocEntry[] | null
  sections: DocSection[]
  issues: BookIssue[]
}

export interface BuildInput {
  cover: PrintBookCover
  options: PrintBookOptions
  blocks: BookBlock[]
}

const CONTENT_KINDS = new Set(['template', 'markdown', 'image'])

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

export function buildDocument(input: BuildInput): BookDocument {
  const { cover, options, blocks } = input
  const issues: BookIssue[] = []
  const sections: DocSection[] = []
  const tocEntries: TocEntry[] = []

  let anchorSeq = 0
  const nextAnchor = (): string => {
    anchorSeq += 1
    return `sec-${pad2(anchorSeq)}`
  }

  /** 相邻分页边界去重：page_break 块只累积为布尔，由下一个章节消费 */
  let pendingBreak = false
  /** 首个章节强制分页（封面/目录之后另起一页） */
  let isFirstSection = true

  /** 判断 heading 是否悬空：其后（跳过 page_break）直到下一个 heading 或结尾都没有内容块 */
  function isDanglingHeading(index: number): boolean {
    for (let i = index + 1; i < blocks.length; i += 1) {
      const type = blocks[i].type
      if (type === 'page_break') continue
      if (type === 'heading') return true
      return !CONTENT_KINDS.has(type)
    }
    return true
  }

  const takeBreak = (extra: boolean): boolean => {
    const brk = isFirstSection || pendingBreak || extra
    pendingBreak = false
    isFirstSection = false
    return brk
  }

  blocks.forEach((block, index) => {
    switch (block.type) {
      case 'page_break':
        pendingBreak = true
        return
      case 'heading': {
        if (isDanglingHeading(index)) {
          issues.push({
            blockIndex: index,
            level: 'warning',
            message: `章节「${block.title}」下没有任何内容`,
          })
        }
        const anchor = nextAnchor()
        const brk = takeBreak(block.heading_level === 1 && options.h1_page_break)
        tocEntries.push({ anchor, title: block.title, level: block.heading_level })
        sections.push({
          kind: 'heading',
          key: block.id,
          anchor,
          title: block.title,
          level: block.heading_level,
          pageBreakBefore: brk,
        })
        return
      }
      case 'template': {
        if (!block.resolved) {
          issues.push({
            blockIndex: index,
            level: 'error',
            message: `模板引用失效（${block.template}），已跳过该节`,
          })
          return
        }
        const info = block.resolved
        const anchor = nextAnchor()
        const title = block.title?.trim() || info.name
        const brk = takeBreak(block.heading_level === 1 && options.h1_page_break)
        const includeBody = block.include_body ?? options.include_body
        const body = includeBody && info.body.trim() ? info.body : null
        const meta: DocMeta | null = options.include_meta
          ? {
              cat: info.cat,
              versionName: info.version_name,
              file: info.file,
              lang: info.lang,
              tags: info.tags,
              src: info.src,
              page: info.page,
              updated: info.updated,
              priority: info.priority,
            }
          : null
        tocEntries.push({ anchor, title, level: block.heading_level })
        sections.push({
          kind: 'template',
          key: block.id,
          anchor,
          title,
          level: block.heading_level,
          pageBreakBefore: brk,
          meta,
          info,
          body,
        })
        return
      }
      case 'markdown': {
        sections.push({
          kind: 'markdown',
          key: block.id,
          pageBreakBefore: takeBreak(false),
          title: block.title,
          content: block.content,
        })
        return
      }
      case 'image': {
        sections.push({
          kind: 'image',
          key: block.id,
          pageBreakBefore: takeBreak(false),
          src: block.src,
          caption: block.caption,
          width: block.width,
        })
        return
      }
    }
  })

  return {
    coverTitle: cover.title,
    subtitle: cover.subtitle,
    author: cover.author,
    logo: cover.logo,
    toc: options.include_toc ? tocEntries : null,
    sections,
    issues,
  }
}
