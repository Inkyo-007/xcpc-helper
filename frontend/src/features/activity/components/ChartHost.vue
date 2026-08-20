<script setup lang="ts">
/** ECharts 生命周期宿主：初始化、尺寸跟随、option 全量更新、点击事件转发。 */

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { echarts, type EChartsCoreOption } from '@/features/activity/model/echarts-setup'

const props = defineProps<{
  option: EChartsCoreOption
}>()

const emit = defineEmits<{
  chartClick: [params: unknown]
}>()

const host = ref<HTMLElement | null>(null)

type Chart = ReturnType<typeof echarts.init>
let chart: Chart | null = null
let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  if (!host.value) return
  chart = echarts.init(host.value, undefined, { renderer: 'svg' })
  chart.setOption(props.option)
  chart.on('click', (params) => emit('chartClick', params))
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(host.value)
})

watch(
  () => props.option,
  (option) => {
    chart?.setOption(option, { notMerge: true })
  },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="host" class="chart-host"></div>
</template>

<style scoped>
.chart-host {
  width: 100%;
  height: 100%;
}
</style>
