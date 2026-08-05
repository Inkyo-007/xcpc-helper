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
