import { describe, expect, it } from 'vitest'
import { groupTemplatesByCategory } from './group'
import type { TemplateAnalyzeItem } from '@/features/transfer/types'

function item(category: string, name: string): TemplateAnalyzeItem {
  return { category, name, version_count: 1, renamed_from: null }
}

describe('groupTemplatesByCategory', () => {
  it('按分类分组并保持组内顺序', () => {
    const groups = groupTemplatesByCategory([
      item('图论', 'dijkstra'),
      item('数学', '快速幂'),
      item('图论', 'tarjan'),
    ])
    // 中文按拼音排序：数学(shuxue) < 图论(tulun)
    expect(groups.map((g) => g.category)).toEqual(['数学', '图论'])
    expect(groups[1].templates.map((t) => t.name)).toEqual(['dijkstra', 'tarjan'])
  })

  it('空列表返回空分组', () => {
    expect(groupTemplatesByCategory([])).toEqual([])
  })
})
