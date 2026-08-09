/** 导入/导出相关类型（与后端 modules/transfer/schemas.py 对齐）。 */

/** 冲突处理策略：跳过 / 覆盖 / 自动重命名 */
export type ConflictStrategy = 'skip' | 'overwrite' | 'rename'

/** 归档识别类型：本软件导出的标准归档 / 外来平铺结构 */
export type ArchiveKind = 'standard' | 'foreign'

export interface TransferWarning {
  path: string
  message: string
}

export interface TemplateAnalyzeItem {
  category: string
  name: string
  version_count: number
  renamed_from: string | null
}

export interface TemplateAnalyzeResult {
  staging_id: string
  kind: ArchiveKind
  category_count: number
  template_count: number
  templates: TemplateAnalyzeItem[]
  warnings: TransferWarning[]
  conflicts: string[]
}

export interface BookAnalyzeItem {
  name: string
  title: string
}

export interface BookAnalyzeResult {
  staging_id: string
  books: BookAnalyzeItem[]
  warnings: TransferWarning[]
  conflicts: string[]
}

export interface RenamedEntry {
  source: string
  target: string
}

export interface FailedEntry {
  id: string
  message: string
}

export interface ImportReport {
  created: string[]
  skipped: string[]
  overwritten: string[]
  renamed: RenamedEntry[]
  failed: FailedEntry[]
}
