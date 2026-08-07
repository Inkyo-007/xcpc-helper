/** 打印册领域类型：与后端 printbook 模块的 API 模型对齐。 */

import type { LangId } from '@/shared/types'

export type BookBlockType = 'heading' | 'template' | 'markdown' | 'image' | 'page_break'

export interface BookBlockBase {
  id: string
  type: BookBlockType
}

/** template 块解析后携带的渲染素材（服务端实时解析并内联返回） */
export interface ResolvedTemplateInfo {
  name: string
  cat: string
  version_name: string
  lang: LangId
  file: string
  code: string
  body: string
  tags: string[]
  src: string | null
  page: string | null
  updated: string | null
  priority: number
}

export interface HeadingBlock extends BookBlockBase {
  type: 'heading'
  title: string
  heading_level: number
}

export interface TemplateBlock extends BookBlockBase {
  type: 'template'
  template: string
  /** null=主版本（第一个版本）；'~'=显式顶层单版本；其余为副标签名 */
  version: string | null
  /** 册内显示名覆盖；null=用模板原名 */
  title: string | null
  heading_level: number
  /** null=跟随册级默认；true/false=显式包含/不包含说明 */
  include_body: boolean | null
  resolved: ResolvedTemplateInfo | null
}

export interface MarkdownBlock extends BookBlockBase {
  type: 'markdown'
  title: string | null
  content: string
}

export interface ImageBlock extends BookBlockBase {
  type: 'image'
  src: string
  caption: string | null
  width: string
}

export interface PageBreakBlock extends BookBlockBase {
  type: 'page_break'
}

export type BookBlock =
  | HeadingBlock
  | TemplateBlock
  | MarkdownBlock
  | ImageBlock
  | PageBreakBlock

export interface PrintBookOptions {
  include_toc: boolean
  include_meta: boolean
  include_body: boolean
  h1_page_break: boolean
}

export interface PrintBookCover {
  title: string
  subtitle: string | null
  author: string | null
  logo: string | null
}

export interface PrintBookDetail {
  name: string
  cover: PrintBookCover
  options: PrintBookOptions
  blocks: BookBlock[]
}

export interface PrintBookSummary {
  name: string
  title: string
  block_count: number
  updated: string
  error: string | null
}
