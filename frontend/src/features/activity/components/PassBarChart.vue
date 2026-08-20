<script setup lang="ts">
/** 通过数柱状图（日 / 月粒度复用）：accent 圆角柱，hover 出 tooltip。 */

import { computed } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import type { BarDatum } from '@/features/activity/model/bars'
import type { EChartsCoreOption } from '@/features/activity/model/echarts-setup'

const props = defineProps<{
  data: BarDatum[]
}>()

const palette = useChartPalette()

const option = computed<EChartsCoreOption>(() => {
  const p = palette.value
  return {
    grid: { left: 4, right: 8, top: 16, bottom: 2, containLabel: true },
    tooltip: {
      trigger: 'item',
      backgroundColor: p.tooltipBg,
      borderWidth: 0,
      textStyle: { color: p.tooltipText, fontSize: 12 },
      extraCssText: 'border-radius:6px;padding:5px 10px;',
      formatter: (params: { dataIndex?: number }) => {
        const d = props.data[params.dataIndex ?? -1]
        return d ? `${d.hint} · 通过 ${d.value} 题` : ''
      },
    },
    xAxis: {
      type: 'category',
      data: props.data.map((d) => d.label),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: p.faint, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: p.border, type: 'dashed' } },
      axisLabel: { color: p.faint, fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: props.data.map((d) => d.value),
        barMaxWidth: 22,
        itemStyle: { color: p.accent, borderRadius: [4, 4, 0, 0] },
        emphasis: { itemStyle: { color: p.heatColors[4] } },
      },
    ],
  }
})
</script>

<template>
  <div class="pass-bar-chart">
    <ChartHost :option="option" />
  </div>
</template>

<style scoped>
.pass-bar-chart {
  height: 168px;
}
</style>
