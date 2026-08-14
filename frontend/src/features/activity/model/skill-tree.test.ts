import { describe, expect, it } from 'vitest'
import { buildPalette } from '@/features/activity/model/echarts-theme'
import {
  buildDomainLegend,
  buildSunburstData,
  buildSunburstOption,
} from '@/features/activity/model/skill-tree'
import type { SkillTreeData } from '@/features/activity/types'

const palette = buildPalette({
  hue: 160,
  dark: false,
  text: '#23211d',
  faint: '#a09a8e',
  surface: '#fdfdfc',
  surface2: '#efede8',
  border: '#e2dfd8',
})

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

describe('buildSunburstData', () => {
  const data = sampleData()
  const [root] = buildSunburstData(data, palette)

  it('返回单根，根值取总计', () => {
    expect(root.name).toBe('技能树')
    expect(root.depth).toBe(0)
    expect(root.value).toBe(data.totals.acCount)
    expect(root.proficiency).toBe(data.totals.proficiency)
  })

  it('域与技能层级对齐输入，且携带展示元数据', () => {
    expect(root.children).toHaveLength(2)
    const [math, dp] = root.children!
    expect(math.name).toBe('数学')
    expect(math.value).toBe(2)
    expect(math.depth).toBe(1)
    expect(math.children).toHaveLength(2)

    const [mathBase, numberTheory] = math.children!
    expect(mathBase.domainKey).toBe('math')
    expect(mathBase.domainName).toBe('数学')
    expect(mathBase.tag).toBe('math')
    expect(mathBase.depth).toBe(2)
    expect(numberTheory.value).toBe(1)

    expect(dp.children).toHaveLength(1)
  })

  it('每个节点都有颜色，且不同域色相不同', () => {
    expect(root.itemStyle.color).toBeTruthy()
    const colors = root.children!.map((d) => d.itemStyle.color)
    expect(new Set(colors).size).toBe(2)
  })
})

describe('buildDomainLegend', () => {
  it('按域顺序生成图例条目，颜色与域色相一致', () => {
    const data = sampleData()
    const legend = buildDomainLegend(data, palette)
    expect(legend).toHaveLength(2)
    expect(legend.map((l) => l.name)).toEqual(['数学', '动态规划'])
    expect(legend[0].color).toBeTruthy()
    expect(legend[0].acCount).toBe(2)
    // 图例身份色取掌握度 1 的满强度色，与域节点的弱化色不同
    const [mathDomain] = buildSunburstData(data, palette)[0].children!
    expect(legend[0].color).not.toBe(mathDomain.itemStyle.color)
  })
})

describe('buildSunburstOption', () => {
  const option = buildSunburstOption(sampleData(), palette) as {
    series: { type: string; data: unknown[]; nodeClick: string; levels: unknown[] }[]
  }

  it('输出 sunburst 单系列并携带下钻交互', () => {
    expect(option.series).toHaveLength(1)
    expect(option.series[0].type).toBe('sunburst')
    expect(option.series[0].nodeClick).toBe('rootToNode')
  })

  it('三级 levels 对应根 / 域 / 技能', () => {
    expect(option.series[0].levels).toHaveLength(3)
  })
})
