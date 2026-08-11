<script setup lang="ts">
/** activity 热力图：ECharts calendar 坐标，着色档位见 model/heatmap.ts。
 * 格子缝隙用面板底色描边模拟，选中格用 accent 描边。
 */

import { computed } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import type { EChartsCoreOption } from '@/features/activity/model/echarts-setup'
import { heatLevel } from '@/features/activity/model/heatmap'
import type { DayActivity } from '@/features/activity/types'

const props = defineProps<{
  daily: DayActivity[]
  selected: string | null
}>()

const emit = defineEmits<{
  select: [date: string]
}>()

const palette = useChartPalette()

const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
const DAY_LABELS = ['日', '一', '二', '三', '四', '五', '六']

interface HeatValue extends Array<unknown> {
  0: string
  1: number
  2: number
}

const option = computed<EChartsCoreOption>(() => {
  const p = palette.value
  const range = [props.daily[0]?.date ?? '', props.daily.at(-1)?.date ?? '']
  return {
    tooltip: {
      backgroundColor: p.tooltipBg,
      borderWidth: 0,
      textStyle: { color: p.tooltipText, fontSize: 12 },
      extraCssText: 'border-radius:6px;padding:5px 10px;',
      formatter: (params: { value?: HeatValue }) => {
        const v = params.value
        if (!v) return ''
        return `${v[0]} · 提交 ${v[2]} 次 · 通过 ${v[1]} 题`
      },
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
        data: props.daily.map((d) => ({
          value: [d.date, d.solved, d.submissions],
          itemStyle: {
            color: p.heatColors[heatLevel(d.submissions, d.solved)],
            borderColor: props.selected === d.date ? p.accent : p.surface,
            borderWidth: props.selected === d.date ? 1.5 : 2,
            borderRadius: 3,
          },
        })),
      },
    ],
  }
})

function onClick(params: unknown): void {
  const value = (params as { value?: HeatValue }).value
  if (value?.[0]) emit('select', value[0])
}
</script>

<template>
  <div class="activity-heatmap">
    <ChartHost :option="option" @chart-click="onClick" />
  </div>
</template>

<style scoped>
.activity-heatmap {
  height: 150px;
}
</style>
