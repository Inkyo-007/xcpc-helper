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
  lang: LangId
  file: string
  cplx: string | null
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

/** 新建模板输入（可视化 CRUD 预留，本期未接入） */
export interface NewTemplateInput {
  name: string
  cat: string
  lang: LangId
  cplx: string
  priority?: number
  src: string
  desc: string
  code: string
}

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
