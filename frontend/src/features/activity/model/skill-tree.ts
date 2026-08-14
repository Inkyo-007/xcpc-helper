/** 技能树径向布局（纯函数）：把技能树数据换算为 SVG 节点坐标与半径。
 * DOM 无关、可单测；颜色与主题桥接在组件层完成（见 components/SkillTree.vue）。
 *
 * 布局：根节点居中；第一环为技能域（顶端正上方起始、顺时针均布）；
 * 第二环为技能，各技能在其所属域的扇形内均布。
 */

import type { SkillTreeData } from '@/features/activity/types'

export interface Vec2 {
  x: number
  y: number
}

/** 一个已布局的节点（根 / 域 / 技能通用） */
export interface RadialNode {
  key: string
  name: string
  proficiency: number
  acCount: number
  maxDifficulty: number | null
  pos: Vec2
  radius: number
}

export interface SkillLayoutNode extends RadialNode {
  /** 所属技能域 key（技能节点） */
  domainKey: string
}

export interface SkillTreeLayout {
  /** 正方形画布边长 */
  size: number
  center: Vec2
  root: RadialNode
  domains: RadialNode[]
  skills: SkillLayoutNode[]
}

/** 节点半径：掌握度越高越大（根 / 域 / 技能三档缩放） */
export function rootRadius(proficiency: number): number {
  return 24 + proficiency * 12
}

export function domainRadius(proficiency: number): number {
  return 13 + proficiency * 14
}

export function skillRadius(proficiency: number): number {
  return 7 + proficiency * 10
}

/** 域角度：顶端正上方（-π/2）起始，顺时针均布 count 个 */
export function domainAngles(count: number): number[] {
  return Array.from({ length: count }, (_, i) => -Math.PI / 2 + (i * 2 * Math.PI) / count)
}

/** 技能角度：在以 domainAngle 为中心、宽为 sector 的扇形内均布 count 个 */
export function skillAngles(domainAngle: number, count: number, sector: number): number[] {
  if (count <= 1) return [domainAngle]
  return Array.from(
    { length: count },
    (_, j) => domainAngle + (j - (count - 1) / 2) * (sector / (count - 1)),
  )
}

function polar(center: Vec2, radius: number, angle: number): Vec2 {
  return {
    x: center.x + radius * Math.cos(angle),
    y: center.y + radius * Math.sin(angle),
  }
}

/** 域环 / 技能环半径占画布边长的比例（技能环更靠外） */
const DOMAIN_RING_RATIO = 0.3
const SKILL_RING_RATIO = 0.47
/** 技能在所属域扇形内的铺展比例（留出扇区间隙） */
const SKILL_SECTOR_RATIO = 0.72

export function buildSkillTreeLayout(data: SkillTreeData, size: number): SkillTreeLayout {
  const center: Vec2 = { x: size / 2, y: size / 2 }
  const domainRing = size * DOMAIN_RING_RATIO
  const skillRing = size * SKILL_RING_RATIO

  const root: RadialNode = {
    key: 'root',
    name: '技能树',
    proficiency: data.totals.proficiency,
    acCount: data.totals.acCount,
    maxDifficulty: data.totals.maxDifficulty,
    pos: { ...center },
    radius: rootRadius(data.totals.proficiency),
  }

  const angles = domainAngles(data.domains.length)
  const domains: RadialNode[] = data.domains.map((d, i) => ({
    key: d.key,
    name: d.name,
    proficiency: d.proficiency,
    acCount: d.acCount,
    maxDifficulty: d.maxDifficulty,
    pos: polar(center, domainRing, angles[i]),
    radius: domainRadius(d.proficiency),
  }))

  const fullSector = data.domains.length > 1 ? (2 * Math.PI) / data.domains.length : 2 * Math.PI
  const sector = fullSector * SKILL_SECTOR_RATIO
  const skills: SkillLayoutNode[] = []
  data.domains.forEach((d, i) => {
    const spread = skillAngles(angles[i], d.skills.length, sector)
    d.skills.forEach((s, j) => {
      skills.push({
        key: s.key,
        name: s.name,
        proficiency: s.proficiency,
        acCount: s.acCount,
        maxDifficulty: s.maxDifficulty,
        domainKey: d.key,
        pos: polar(center, skillRing, spread[j]),
        radius: skillRadius(s.proficiency),
      })
    })
  })

  return { size, center, root, domains, skills }
}
