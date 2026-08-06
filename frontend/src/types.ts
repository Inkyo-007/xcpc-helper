/** 与后端 API 对齐的领域类型。分类与语言由后端按目录/扩展名动态识别，均为 string。 */

export type SortMode = 'updated' | 'name' | 'priority'

export type LangId = string

export interface Category {
  /** 分类目录名；'all' 为前端内置的"全部"选项 */
  id: string
  name: string
  hue: number | null
  count?: number
}

/** 列表页摘要：与后端 TemplateSummary 对应，不含代码与说明正文 */
export interface TemplateSummary {
  id: string
  name: string
  cat: string
  /** 主版本语言；空模板（无版本）时为 null */
  lang: LangId | null
  /** 主版本文件名；空模板（无版本）时为 null */
  file: string | null
  tags: string[]
  src: string | null
  page: string | null
  updated: string | null
  priority: number
  variant_count: number
}

/** 详情页中的一个版本（副标签），body 为该版本 README 正文 */
export interface TemplateVariant {
  id: string
  name: string
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

/** 详情：与后端 TemplateDetail 对应 */
export interface TemplateDetail extends TemplateSummary {
  desc: string
  variants: TemplateVariant[]
}

/** 扫描诊断：content/ 中的格式问题 */
export interface DiagnosticItem {
  level: 'error' | 'warning'
  path: string
  message: string
}

/** 新建空主标签输入：与后端 TemplateCreate 对应 */
export interface TemplateCreateInput {
  category: string
  name: string
}

/** 版本元数据输入：与后端 VersionMetaInput 对应 */
export interface VersionMetaPayload {
  /** ISO 日期（2026-08-05），不填为 null */
  updated: string | null
  tags: string[]
  source: string | null
  page: string | null
  priority: number
}

/** 新建/更新版本请求体：与后端 VersionUpsert 对应 */
export interface VersionUpsertPayload {
  /** 副标签名；新建必填，顶层单版本更新时为 null */
  name: string | null
  /** 代码文件名；为 null 时后端默认 code.<ext> */
  file: string | null
  /** 代码扩展名（不含点），如 cpp / c / py / java */
  ext: string
  code: string
  meta: VersionMetaPayload
  /** README 正文（Markdown） */
  body: string
}

/** URL 中寻址顶层单版本的保留字（与后端 ROOT_VERSION_TOKEN 一致） */
export const ROOT_VERSION_TOKEN = '~'

export type PageId = 'lib' | 'books' | 'io' | 'stress' | 'gen' | 'settings'

export interface NavChild {
  id: string
  label: string
  page: PageId
}

export interface NavGroup {
  id: string
  label: string
  icon: 'template' | 'timer' | 'settings'
  badge?: string
  page?: PageId
  children?: NavChild[]
}

export interface PlaceholderMeta {
  group: string
  sub: string
  icon: 'book' | 'import' | 'timer' | 'settings'
  title: string
  hint: string
}

/* ============ 打印册（原型阶段，与后端 print_book 设计对齐） ============ */

export type BookBlockType = 'heading' | 'template' | 'markdown' | 'image' | 'page_break'

export interface BookBlockBase {
  id: string
  type: BookBlockType
}

/** template 块解析后携带的渲染素材（原型阶段直接内联） */
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
