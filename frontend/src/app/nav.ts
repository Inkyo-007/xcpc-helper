/** 应用级导航配置与类型：侧边栏分组、页面标识与占位页文案。 */

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

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'templates',
    label: '模板整理',
    icon: 'template',
    children: [
      { id: 'tpl-lib', label: '模板库', page: 'lib' },
      { id: 'tpl-books', label: '打印册', page: 'books' },
      { id: 'tpl-io', label: '导入 / 导出', page: 'io' },
    ],
  },
  {
    id: 'contest',
    label: '比赛工具',
    icon: 'timer',
    badge: '规划中',
    children: [
      { id: 'stress', label: '对拍器', page: 'stress' },
      { id: 'gen', label: '数据生成', page: 'gen' },
    ],
  },
  {
    id: 'settings',
    label: '设置',
    icon: 'settings',
    badge: '规划中',
    page: 'settings',
  },
]

export const PLACEHOLDER_PAGES: Record<Exclude<PageId, 'lib'>, PlaceholderMeta> = {
  books: {
    group: '模板整理',
    sub: '打印册',
    icon: 'book',
    title: '打印册',
    hint: '勾选模板、拖拽排序，一键生成带目录的 Markdown 与 PDF。此功能在 M2 里程碑实现。',
  },
  io: {
    group: '模板整理',
    sub: '导入 / 导出',
    icon: 'import',
    title: '导入 / 导出',
    hint: '批量导入本地目录（目录自动映射为分类），或整库备份 / 迁移。此功能在 M2 里程碑实现。',
  },
  stress: {
    group: '比赛工具',
    sub: '对拍器',
    icon: 'timer',
    title: '对拍器',
    hint: '规划中：挂上暴力与正解，随机数据自动对拍。',
  },
  gen: {
    group: '比赛工具',
    sub: '数据生成',
    icon: 'timer',
    title: '数据生成',
    hint: '规划中：按约束生成随机测试数据。',
  },
  settings: {
    group: '设置',
    sub: '',
    icon: 'settings',
    title: '设置',
    hint: '规划中：数据目录、备份策略、默认语言等。',
  },
}
