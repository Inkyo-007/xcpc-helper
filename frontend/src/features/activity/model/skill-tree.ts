/** 技能树可视化（纯函数）：把技能树数据换算为 ECharts sunburst（旭日图）的数据与 option。
 * DOM 无关、可单测；颜色来自主题桥接的调色板（见 echarts-theme.ts 的 domainHues / domainFill）。
 *
 * 视觉编码：
 * - 扇区面积 ∝ acCount（练得越多扇区越大）；
 * - 颜色：12 个技能域各取一个分类色相（随主题 --hue 旋转），掌握度驱动明度/饱和度
 *   （掌握度越高越鲜艳明亮）；
 * - 结构：根（中心）→ 技能域（第一环）→ 技能（第二环），固定 DOMAIN_ORDER 顺时针排布；
 * - 交互：悬停高亮该子树、点击领域下钻、点击中心返回（nodeClick: rootToNode）。
 */

import { domainFill, type ChartPalette } from '@/features/activity/model/echarts-theme'
import type { EChartsCoreOption } from '@/features/activity/model/echarts-setup'
import type { SkillTreeData } from '@/features/activity/types'

/** 旭日图数据节点（ECharts sunburst data 项 + 展示元数据） */
export interface SunburstNode {
  name: string
  value: number
  itemStyle: { color: string }
  children?: SunburstNode[]
  /** 掌握度 0~1 */
  proficiency: number
  acCount: number
  maxDifficulty: number | null
  /** 所属技能域 key（技能节点） */
  domainKey?: string
  /** 所属技能域中文名（技能节点，tooltip 展示） */
  domainName?: string
  /** 原 CF 标签（技能节点） */
  tag?: string
  /** 树深度：0=根 1=域 2=技能 */
  depth: 0 | 1 | 2
}

/** 图例条目：技能域的身份色（掌握度 1 的满强度色） */
export interface DomainLegendItem {
  key: string
  name: string
  acCount: number
  proficiency: number
  color: string
}

function pct(p: number): string {
  return `${Math.round(p * 100)}%`
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 由技能树数据构建旭日图数据（返回单根数组，ECharts sunburst 约定） */
export function buildSunburstData(data: SkillTreeData, palette: ChartPalette): SunburstNode[] {
  const root: SunburstNode = {
    name: '技能树',
    value: data.totals.acCount,
    itemStyle: { color: palette.accent },
    proficiency: data.totals.proficiency,
    acCount: data.totals.acCount,
    maxDifficulty: data.totals.maxDifficulty,
    depth: 0,
  }

  root.children = data.domains.map((d, i) => {
    const hue = palette.domainHues[i % palette.domainHues.length]
    const domain: SunburstNode = {
      name: d.name,
      value: d.acCount,
      itemStyle: { color: domainFill(hue, d.proficiency, palette.dark) },
      proficiency: d.proficiency,
      acCount: d.acCount,
      maxDifficulty: d.maxDifficulty,
      domainKey: d.key,
      depth: 1,
    }
    domain.children = d.skills.map((s) => ({
      name: s.name,
      value: s.acCount,
      itemStyle: { color: domainFill(hue, s.proficiency, palette.dark) },
      proficiency: s.proficiency,
      acCount: s.acCount,
      maxDifficulty: s.maxDifficulty,
      domainKey: d.key,
      domainName: d.name,
      tag: s.tag,
      depth: 2,
    }))
    return domain
  })

  return [root]
}

/** 构建图例数据（与 buildSunburstData 用同一套色相，保证图例 ↔ 图表一致） */
export function buildDomainLegend(
  data: SkillTreeData,
  palette: ChartPalette,
): DomainLegendItem[] {
  return data.domains.map((d, i) => {
    const hue = palette.domainHues[i % palette.domainHues.length]
    return {
      key: d.key,
      name: d.name,
      acCount: d.acCount,
      proficiency: d.proficiency,
      color: domainFill(hue, 1, palette.dark),
    }
  })
}

function tooltipHtml(node: SunburstNode): string {
  const meta = [`AC ${node.acCount} 题`]
  if (node.maxDifficulty != null) meta.push(`最高 ${node.maxDifficulty}`)
  meta.push(`掌握 ${pct(node.proficiency)}`)
  const sub =
    node.depth === 2 && node.domainName
      ? `<div style="opacity:.6;font-size:11px;margin-bottom:2px">${escapeHtml(node.domainName)}</div>`
      : ''
  return (
    `<div style="font-weight:600;margin-bottom:1px">${escapeHtml(node.name)}</div>` +
    sub +
    `<div style="opacity:.85;font-size:11px">${meta.join(' · ')}</div>`
  )
}

/** 由技能树数据与调色板构建完整 ECharts option */
export function buildSunburstOption(data: SkillTreeData, palette: ChartPalette): EChartsCoreOption {
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: palette.tooltipBg,
      borderWidth: 0,
      textStyle: { color: palette.tooltipText, fontSize: 12 },
      extraCssText:
        'border-radius:8px;padding:7px 11px;box-shadow:0 6px 20px rgb(20 16 10 / 0.25);',
      formatter: (params: { data?: SunburstNode }) => (params.data ? tooltipHtml(params.data) : ''),
    },
    series: [
      {
        type: 'sunburst',
        data: buildSunburstData(data, palette),
        radius: ['15%', '92%'],
        center: ['50%', '50%'],
        // 保持后端 DOMAIN_ORDER 固定顺序（V8 稳定排序：比较恒为 0 即不重排）
        sort: () => 0,
        nodeClick: 'rootToNode',
        emphasis: { focus: 'descendant' },
        itemStyle: {
          borderColor: palette.surface,
          borderWidth: 2,
        },
        levels: [
          {
            // 根（下钻后为当前聚焦的域）
            label: {
              formatter: (p: { data?: SunburstNode }) =>
                p.data ? `${p.data.name}\n${pct(p.data.proficiency)}` : '',
              fontSize: 15,
              fontWeight: 700,
              color: palette.text,
            },
          },
          {
            // 第一环：技能域
            label: {
              rotate: 'radial',
              minAngle: 5,
              fontSize: 12,
              fontWeight: 600,
              color: palette.text,
            },
          },
          {
            // 第二环：技能
            label: {
              rotate: 'radial',
              minAngle: 18,
              fontSize: 11,
              color: palette.faint,
            },
          },
        ],
      },
    ],
  }
}
