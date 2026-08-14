import { describe, expect, it } from 'vitest'
import type { SkillTreeData } from '@/features/activity/types'
import {
  buildSkillTreeLayout,
  domainAngles,
  domainRadius,
  rootRadius,
  skillAngles,
  skillRadius,
} from '@/features/activity/model/skill-tree'

function sampleData(): SkillTreeData {
  return {
    totals: { acCount: 3, proficiency: 0.6, maxDifficulty: 1600 },
    domains: [
      {
        key: 'math',
        name: '数学',
        proficiency: 0.6,
        acCount: 2,
        maxDifficulty: 1600,
        skills: [
          { key: 'math', name: '数学基础', tag: 'math', proficiency: 0.6, acCount: 2, maxDifficulty: 1600 },
          { key: 'number theory', name: '数论', tag: 'number theory', proficiency: 0.2, acCount: 1, maxDifficulty: 800 },
        ],
      },
      {
        key: 'dp',
        name: '动态规划',
        proficiency: 0.3,
        acCount: 1,
        maxDifficulty: 1200,
        skills: [{ key: 'dp', name: '动态规划', tag: 'dp', proficiency: 0.3, acCount: 1, maxDifficulty: 1200 }],
      },
    ],
  }
}

describe('domainAngles', () => {
  it('起始于正上方（-π/2）并覆盖整圆', () => {
    const a = domainAngles(4)
    expect(a[0]).toBeCloseTo(-Math.PI / 2)
    expect(a.length).toBe(4)
    // 相邻角度差一致
    const step = a[1] - a[0]
    for (let i = 1; i < a.length; i++) expect(a[i] - a[i - 1]).toBeCloseTo(step)
  })

  it('空域返回空数组', () => {
    expect(domainAngles(0)).toEqual([])
  })
})

describe('skillAngles', () => {
  it('单个技能落在域角度上', () => {
    expect(skillAngles(0, 1, 1)).toEqual([0])
  })

  it('多个技能以域角度为中心对称铺开', () => {
    const a = skillAngles(0, 3, 1)
    expect(a).toHaveLength(3)
    expect(a[1]).toBeCloseTo(0) // 中间技能对准域中心
    expect(a[0]).toBeLessThan(0)
    expect(a[2]).toBeGreaterThan(0)
    // 对称
    expect(a[0] + a[2]).toBeCloseTo(0)
  })
})

describe('node radius', () => {
  it('半径随掌握度单调递增', () => {
    expect(rootRadius(1)).toBeGreaterThan(rootRadius(0))
    expect(domainRadius(1)).toBeGreaterThan(domainRadius(0))
    expect(skillRadius(1)).toBeGreaterThan(skillRadius(0))
  })
})

describe('buildSkillTreeLayout', () => {
  const size = 800
  const layout = buildSkillTreeLayout(sampleData(), size)

  it('根节点居中', () => {
    expect(layout.root.pos).toEqual({ x: size / 2, y: size / 2 })
  })

  it('域与技能节点数对齐输入', () => {
    expect(layout.domains).toHaveLength(2)
    expect(layout.skills).toHaveLength(3)
  })

  it('域节点落在域环半径附近', () => {
    for (const d of layout.domains) {
      const dx = d.pos.x - layout.center.x
      const dy = d.pos.y - layout.center.y
      expect(Math.hypot(dx, dy)).toBeCloseTo(size * 0.3, 0)
    }
  })

  it('技能节点落在技能环半径附近并关联所属域', () => {
    for (const s of layout.skills) {
      const dx = s.pos.x - layout.center.x
      const dy = s.pos.y - layout.center.y
      expect(Math.hypot(dx, dy)).toBeCloseTo(size * 0.47, 0)
      expect(['math', 'dp']).toContain(s.domainKey)
    }
    const mathSkills = layout.skills.filter((s) => s.domainKey === 'math')
    expect(mathSkills).toHaveLength(2)
  })
})
