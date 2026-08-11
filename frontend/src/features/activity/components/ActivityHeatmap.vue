<script setup lang="ts">
/** activity 热力图：ECharts calendar 坐标 + piecewise visualMap 着色。
 * 着色档位见 model/heatmap.ts；档位值直接编码进 data 第二维，由隐藏
 * visualMap 映射为颜色（heatmap 系列必须搭配 visualMap，缺了 dev 下会抛错）。
 * 格子缝隙用面板底色描边模拟，选中格用 accent 描边。
 */

import { computed } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import { buildHeatmapOption, type HeatValue } from '@/features/activity/model/heatmap-option'
import type { DayActivity } from '@/features/activity/types'

const props = defineProps<{
  daily: DayActivity[]
  selected: string | null
}>()

const emit = defineEmits<{
  select: [date: string]
}>()

const palette = useChartPalette()

const option = computed(() => buildHeatmapOption(props.daily, props.selected, palette.value))

function onClick(params: unknown): void {
  const value = (params as { value?: HeatValue }).value
  if (value?.[0]) emit('select', value[0])
}
</script>

<template>
  <div class="activity-heatmap">
    <ChartHost v-if="daily.length" :option="option" @chart-click="onClick" />
    <div v-else class="heatmap-empty">该时间范围内暂无训练数据</div>
  </div>
</template>

<style scoped>
.activity-heatmap {
  height: 150px;
}

.heatmap-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--faint);
}
</style>
