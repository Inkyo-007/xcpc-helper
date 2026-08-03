import type { Category, TemplateCategory } from '@/types'

export const CATEGORIES: Category[] = [
  { id: 'all', name: '全部', hue: null },
  { id: 'ds', name: '数据结构', hue: 160 },
  { id: 'graph', name: '图论', hue: 25 },
  { id: 'string', name: '字符串', hue: 280 },
  { id: 'math', name: '数学', hue: 200 },
  { id: 'dp', name: '动态规划', hue: 340 },
  { id: 'misc', name: '其他', hue: 80 },
]

export function categoryOf(id: TemplateCategory): Category {
  return CATEGORIES.find((c) => c.id === id) ?? CATEGORIES[CATEGORIES.length - 1]
}

export function categoryHue(id: TemplateCategory): number {
  return categoryOf(id).hue ?? 160
}

export const LANG_OPTIONS = [
  { label: 'C++', value: 'cpp' },
  { label: 'Python', value: 'py' },
  { label: 'Java', value: 'java' },
  { label: 'C', value: 'c' },
] as const
