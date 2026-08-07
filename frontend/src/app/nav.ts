/** 应用级导航配置：侧边栏分组。to 路径与 router.ts 中的路由一一对应。 */

export interface NavChild {
  id: string
  label: string
  /** 路由路径 */
  to: string
}

export interface NavGroup {
  id: string
  label: string
  icon: 'template' | 'timer' | 'settings'
  badge?: string
  to?: string
  children?: NavChild[]
}

export interface PlaceholderMeta {
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
      { id: 'tpl-lib', label: '模板库', to: '/template/library' },
      { id: 'tpl-books', label: '打印册', to: '/template/printbook' },
      { id: 'tpl-io', label: '导入 / 导出', to: '/template/io' },
    ],
  },
  {
    id: 'contest',
    label: '比赛工具',
    icon: 'timer',
    badge: '规划中',
    children: [
      { id: 'stress', label: '对拍器', to: '/contest/stress' },
      { id: 'gen', label: '数据生成', to: '/contest/gen' },
    ],
  },
  {
    id: 'settings',
    label: '设置',
    icon: 'settings',
    badge: '规划中',
    to: '/settings',
  },
]
