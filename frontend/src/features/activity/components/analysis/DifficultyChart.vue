<script setup lang="ts">
/** 难度分布横向条形图：通过 / 尝试双系列，颜色经主题桥接（useChartPalette）。 */

import { computed } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import { buildDifficultyOption } from '@/features/activity/model/analysis'
import type { DifficultyBand } from '@/features/activity/types'

const props = defineProps<{
  bands: DifficultyBand[]
}>()

const palette = useChartPalette()

const option = computed(() => buildDifficultyOption(props.bands, palette.value))
</script>

<template>
  <div class="difficulty-chart">
    <ChartHost :option="option" />
  </div>
</template>

<style scoped>
.difficulty-chart {
  height: 240px;
}
</style>
