export type CategoryId = 'all' | 'ds' | 'graph' | 'string' | 'math' | 'dp' | 'misc'

export type TemplateCategory = Exclude<CategoryId, 'all'>

export type LangId = 'cpp' | 'py' | 'java' | 'c'

export interface Category {
  id: CategoryId
  name: string
  hue: number | null
}

export interface Template {
  id: number
  name: string
  cat: TemplateCategory
  lang: LangId
  file: string
  cplx: string
  tags: string[]
  src: string
  updated: string
  priority: number
  desc: string
  code: string
  lastUsedAt: string | null
  variants?: TemplateVariant[]
}

export interface TemplateVariant {
  id: string
  name: string
  lang: LangId
  file: string
  code: string
}

export type SortMode = 'updated' | 'name' | 'priority'

export interface NewTemplateInput {
  name: string
  cat: TemplateCategory
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
