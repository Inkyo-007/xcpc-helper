import { describe, expect, it } from 'vitest'
import { buildPalette } from '@/features/activity/model/echarts-theme'
import {
  buildDifficultyOption,
  buildRhythmOption,
  buildVerdictOption,
  buildWeakPointGroups,
  percentText,
  totalSubmissions,
  verdictColor,
} from '@/features/activity/model/analysis'
import type {
  DifficultyBand,
  Rhythm,
  Verdict,
  VerdictCount,
  WeakPoint,
} from '@/features/activity/types'

const palette = buildPalette({
  hue: 160,
  dark: false,
  text: '#23211d',
  faint: '#a09a8e',
  surface: '#fdfdfc',
  surface2: '#efede8',
  border: '#e2dfd8',
})

const bands: DifficultyBand[] = [
  { label: '≤1199', min: null, max: 1199, solvedCount: 3, attemptCount: 5, submissionCount: 8, passRate: 0.6 },
  { label: '1200–1399', min: 1200, max: 1399, solvedCount: 1, attemptCount: 4, submissionCount: 6, passRate: 0.25 },
  { label: '未知', min: null, max: null, solvedCount: 0, attemptCount: 2, submissionCount: 2, passRate: 0 },
]

const verdicts: VerdictCount[] = [
  { verdict: 'AC', count: 6, share: 0.6 },
  { verdict: 'WA', count: 3, share: 0.3 },
  { verdict: 'CE', count: 0, share: 0 },
  { verdict: 'JG', count: 1, share: 0.1 },
]

const rhythm: Rhythm = {
  weeks: [
    { weekStart: '2026-01-05', solved: 2, attempts: 5, activeDays: 2 },
    { weekStart: '2026-01-12', solved: 3, attempts: 4, activeDays: 3 },
  ],
  hours: [
    { hour: 9, count: 2 },
    { hour: 21, count: 5 },
  ],
}

const weakPoints: WeakPoint[] = [
  {
    key: 'dp', name: '动态规划', domainKey: 'dp', domainName: '动态规划',
    solvedCount: 1, attemptCount: 5, passRate: 0.2, proficiency: 0.3, maxDifficulty: 1200,
    suggestion: '基础薄弱，建议从该标签入门题系统刷起',
  },
  {
    key: 'math', name: '数学基础', domainKey: 'math', domainName: '数学',
    solvedCount: 3, attemptCount: 4, passRate: 0.75, proficiency: 0.7, maxDifficulty: 1600,
    suggestion: '接近熟练，可上难度挑战',
  },
  {
    key: 'number theory', name: '数论', domainKey: 'math', domainName: '数学',
    solvedCount: 0, attemptCount: 2, passRate: 0, proficiency: 0.1, maxDifficulty: null,
    suggestion: '基础薄弱，建议从该标签入门题系统刷起',
  },
]

type SeriesLike = { name: string; type: string; data: unknown[]; itemStyle: { color: string } }

describe('percentText', () => {
  it('把 0~1 比值换算为百分比文案', () => {
    expect(percentText(0.6)).toBe('60%')
    expect(percentText(0.25)).toBe('25%')
    expect(percentText(0)).toBe('0%')
  })
})

describe('verdictColor', () => {
  it('verdict 语义色固定映射（与活动页徽章一致）', () => {
    expect(verdictColor('AC')).toBe('#1e9e52')
    expect(verdictColor('WA')).toBe('#d64541')
    expect(verdictColor('CE')).toBe('#c28a0a')
    expect(verdictColor('RE')).toBe('#8a5cf0')
    expect(verdictColor('JG')).toBe('#2b8fc8')
    expect(verdictColor('TLE')).toBe('#2f5fc7')
    expect(verdictColor('MLE')).toBe('#2f5fc7')
    expect(verdictColor('OLE')).toBe('#2f5fc7')
    expect(verdictColor('UKE')).toBe('#2f5fc7')
  })
})

describe('totalSubmissions', () => {
  it('汇总全部 verdict 计数', () => {
    expect(totalSubmissions(verdicts)).toBe(10)
    expect(totalSubmissions([])).toBe(0)
  })
})

describe('buildDifficultyOption', () => {
  const option = buildDifficultyOption(bands, palette) as {
    yAxis: { data: string[] }
    series: SeriesLike[]
  }

  it('横向条形图：y 轴为档位标签，双系列名与数据映射正确', () => {
    expect(option.yAxis.data).toEqual(bands.map((b) => b.label))
    expect(option.series).toHaveLength(2)

    const attempts = option.series.find((s) => s.name === '尝试')!
    const solved = option.series.find((s) => s.name === '通过')!
    expect(attempts.data).toEqual(bands.map((b) => b.attemptCount))
    expect(solved.data).toEqual(bands.map((b) => b.solvedCount))
    expect(option.series.every((s) => s.type === 'bar')).toBe(true)
  })

  it('配色经主题桥接（尝试取热度中间档、通过取 accent，不写死）', () => {
    const attempts = option.series.find((s) => s.name === '尝试')!
    const solved = option.series.find((s) => s.name === '通过')!
    expect(attempts.itemStyle.color).toBe(palette.heatColors[3])
    expect(solved.itemStyle.color).toBe(palette.accent)
  })
})

describe('buildVerdictOption', () => {
  const option = buildVerdictOption(verdicts, palette) as {
    series: { type: string; radius: string[]; data: { name: Verdict; value: number; itemStyle: { color: string } }[] }[]
    title: { text: string; subtext: string }
  }

  it('过滤 count==0 的项，只保留有提交的 verdict', () => {
    const names = option.series[0].data.map((d) => d.name)
    expect(names).toEqual(['AC', 'WA', 'JG'])
  })

  it('环形饼图：每个切片的颜色与语义色一致，数值映射正确', () => {
    expect(option.series[0].type).toBe('pie')
    expect(option.series[0].radius.length).toBe(2)
    expect(option.series[0].radius[0]).not.toBe(option.series[0].radius[1])
    for (const d of option.series[0].data) {
      expect(d.itemStyle.color).toBe(verdictColor(d.name))
    }
    const ac = option.series[0].data.find((d) => d.name === 'AC')!
    expect(ac.value).toBe(6)
  })

  it('中心显示总提交数', () => {
    expect(option.title.text).toBe(String(totalSubmissions(verdicts)))
    expect(option.title.subtext).toBe('总提交')
  })
})

describe('buildRhythmOption', () => {
  const option = buildRhythmOption(rhythm, palette) as {
    series: SeriesLike[]
    xAxis: { data: string[] }[]
  }

  it('近 12 周双系列（通过 / 提交）数据映射正确', () => {
    const solved = option.series.find((s) => s.name === '通过')!
    const attempts = option.series.find((s) => s.name === '提交')!
    expect(solved.data).toEqual(rhythm.weeks.map((w) => w.solved))
    expect(attempts.data).toEqual(rhythm.weeks.map((w) => w.attempts))
  })

  it('活跃时段为 0~23 单系列，缺失小时补 0', () => {
    const hours = option.series.find((s) => s.name === '活跃时段')!
    expect(hours.data).toHaveLength(24)
    expect(hours.data[9]).toBe(2)
    expect(hours.data[21]).toBe(5)
    expect(hours.data[0]).toBe(0)
  })

  it('x 轴为周标签（MM-DD）与 0~23 小时', () => {
    expect(option.xAxis[0].data).toEqual(rhythm.weeks.map((w) => w.weekStart.slice(5)))
    expect(option.xAxis[1].data).toHaveLength(24)
    expect(option.xAxis[1].data[0]).toBe('0')
  })

  it('配色经主题桥接（不写死颜色）', () => {
    const solved = option.series.find((s) => s.name === '通过')!
    const attempts = option.series.find((s) => s.name === '提交')!
    const hours = option.series.find((s) => s.name === '活跃时段')!
    expect(solved.itemStyle.color).toBe(palette.accent)
    expect(attempts.itemStyle.color).toBe(palette.heatColors[3])
    expect(hours.itemStyle.color).toBe(palette.heatColors[4])
  })
})

describe('buildWeakPointGroups', () => {
  it('按 domainKey 分组并保持 domainName 与输入顺序', () => {
    const groups = buildWeakPointGroups(weakPoints)
    expect(groups.map((g) => g.domainKey)).toEqual(['dp', 'math'])
    expect(groups[0].domainName).toBe('动态规划')
    expect(groups[1].domainName).toBe('数学')
    expect(groups[0].items).toHaveLength(1)
    expect(groups[1].items).toHaveLength(2)
    expect(groups[1].items.map((i) => i.key)).toEqual(['math', 'number theory'])
  })

  it('空数组返回空分组', () => {
    expect(buildWeakPointGroups([])).toEqual([])
  })
})
