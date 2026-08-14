<script setup lang="ts">
/** 训练节奏图：近 12 周柱状图（通过 / 提交双系列）+ 活跃时段（0~23 小时）单系列，
 *  由单个 option（双 grid）承载，颜色经主题桥接（useChartPalette）。 */

import { computed } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import { buildRhythmOption } from '@/features/activity/model/analysis'
import type { Rhythm } from '@/features/activity/types'

const props = defineProps<{
  rhythm: Rhythm
}>()

const palette = useChartPalette()

const option = computed(() => buildRhythmOption(props.rhythm, palette.value))
</script>

<template>
  <div class="rhythm-chart">
    <ChartHost :option="option" />
  </div>
</template>

<style scoped>
.rhythm-chart {
  height: 300px;
}
</style>
