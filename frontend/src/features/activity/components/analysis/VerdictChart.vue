<script setup lang="ts">
/** 提交质量环形饼图：verdict 语义色 + 中心总提交数，颜色经主题桥接（useChartPalette）。 */

import { computed } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import { buildVerdictOption } from '@/features/activity/model/analysis'
import type { VerdictCount } from '@/features/activity/types'

const props = defineProps<{
  verdicts: VerdictCount[]
}>()

const palette = useChartPalette()

const option = computed(() => buildVerdictOption(props.verdicts, palette.value))
</script>

<template>
  <div class="verdict-chart">
    <ChartHost :option="option" />
  </div>
</template>

<style scoped>
.verdict-chart {
  height: 240px;
}
</style>
