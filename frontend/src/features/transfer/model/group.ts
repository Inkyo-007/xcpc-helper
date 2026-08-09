/** analyze 结果的展示组装（纯函数）。 */

import type { TemplateAnalyzeItem } from '@/features/transfer/types'

export interface CategoryGroup {
  category: string
  templates: TemplateAnalyzeItem[]
}

/** 把识别出的模板按分类分组，分类按中文排序，组内保持后端返回顺序。 */
export function groupTemplatesByCategory(items: TemplateAnalyzeItem[]): CategoryGroup[] {
  const map = new Map<string, TemplateAnalyzeItem[]>()
  for (const item of items) {
    const list = map.get(item.category) ?? []
    list.push(item)
    map.set(item.category, list)
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b, 'zh-Hans-CN'))
    .map(([category, templates]) => ({ category, templates }))
}
