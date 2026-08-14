/** 路由表：应用导航的事实来源。侧边栏选中态与顶栏面包屑均由路由 meta 驱动。 */

import { createRouter, createWebHistory } from 'vue-router'
import type { PlaceholderMeta } from '@/app/nav'

declare module 'vue-router' {
  interface RouteMeta {
    /** 顶栏面包屑：所属功能组 */
    group?: string
    /** 顶栏面包屑：子页名 */
    sub?: string
    /** 占位页文案；供尚未实现的功能页使用 */
    placeholder?: PlaceholderMeta
  }
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/template/library' },
    {
      path: '/template/library',
      component: () => import('@/features/template/TemplateLibraryPage.vue'),
      meta: { group: '模板整理', sub: '模板库' },
    },
    {
      path: '/template/printbook',
      component: () => import('@/features/printbook/PrintBookPage.vue'),
      meta: { group: '模板整理', sub: '打印册' },
    },
    {
      path: '/activity/overview',
      component: () => import('@/features/activity/ActivityPage.vue'),
      meta: { group: '训练统计', sub: '数据总览' },
    },
    {
      path: '/activity/skill-tree',
      component: () => import('@/features/activity/SkillTreePage.vue'),
      meta: { group: '训练统计', sub: '技能树' },
    },
    {
      path: '/contest/stress',
      component: () => import('@/app/PlaceholderPage.vue'),
      meta: {
        group: '比赛工具',
        sub: '对拍器',
        placeholder: {
          icon: 'timer',
          title: '对拍器',
          hint: '规划中：挂上暴力与正解，随机数据自动对拍。',
        },
      },
    },
    {
      path: '/contest/gen',
      component: () => import('@/app/PlaceholderPage.vue'),
      meta: {
        group: '比赛工具',
        sub: '数据生成',
        placeholder: {
          icon: 'timer',
          title: '数据生成',
          hint: '规划中：按约束生成随机测试数据。',
        },
      },
    },
    {
      path: '/settings',
      component: () => import('@/app/PlaceholderPage.vue'),
      meta: {
        group: '设置',
        sub: '',
        placeholder: {
          icon: 'settings',
          title: '设置',
          hint: '规划中：数据目录、备份策略、默认语言等。',
        },
      },
    },
    { path: '/:pathMatch(.*)*', redirect: '/template/library' },
  ],
})
