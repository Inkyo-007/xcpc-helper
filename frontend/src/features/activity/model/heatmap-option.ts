
/** 日历热力图的 option 构建（纯函数）：着色档位编码进 data 第二维，
 * 由隐藏的 piecewise visualMap 映射为颜色——heatmap 系列必须搭配
 * visualMap 使用，缺失时开发模式会直接抛 "Heatmap must use with visualMap"。
 */

import type { EChartsCoreOption } from '@/features/activity/model/echarts-setup'
import type { ChartPalette } from '@/features/activity/model/echarts-theme'
import { heatLevel } from '@/features/activity/model/heatmap'
import type { DayActivity } from '@/features/activity/types'

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
const DAY_LABELS = ['日', '一', '二', '三', '四', '五', '六']

/** data 一行的形状：[日期, 档位, AC 数, 提交数] */
export interface HeatValue extends Array<unknown> {
  0: string
  1: number
  2: number
  3: number
}

export function buildHeatmapOption(
  daily: DayActivity[],
  selected: string | null,
  p: ChartPalette,
): EChartsCoreOption {
  const range = [daily[0]?.date ?? '', daily.at(-1)?.date ?? '']
  return {
    tooltip: {
      backgroundColor: p.tooltipBg,
      borderWidth: 0,
      textStyle: { color: p.tooltipText, fontSize: 12 },
      extraCssText: 'border-radius:6px;padding:5px 10px;',
      formatter: (params: { value?: HeatValue }) => {
        const v = params.value
        if (!v) return ''
        return `${v[0]} · 提交 ${v[3]} 次 · 通过 ${v[2]} 题`
      },
    },
    visualMap: {
      show: false,
      type: 'piecewise',
      seriesIndex: 0,
      dimension: 1,
      pieces: p.heatColors.map((color, i) => ({ value: i, color })),
    },
    calendar: {
      top: 26,
      left: 34,
      right: 12,
      bottom: 6,
      range,
      cellSize: ['auto', 14],
      splitLine: { show: false },
      itemStyle: { color: 'transparent', borderWidth: 0 },
      dayLabel: { firstDay: 1, nameMap: DAY_LABELS, color: p.faint, fontSize: 11 },
      monthLabel: { nameMap: MONTH_LABELS, color: p.faint, fontSize: 11 },
      yearLabel: { show: false },
    },
    series: [
      {
        type: 'heatmap',
        coordinateSystem: 'calendar',
        emphasis: { disabled: true },
        data: daily.map((d) => ({
          value: [d.date, heatLevel(d.submissions, d.solved), d.solved, d.submissions],
          itemStyle: {
            borderColor: selected === d.date ? p.accent : p.surface,
            borderWidth: selected === d.date ? 1.5 : 2,
            borderRadius: 3,
          },
        })),
      },
    ],
  }
}
