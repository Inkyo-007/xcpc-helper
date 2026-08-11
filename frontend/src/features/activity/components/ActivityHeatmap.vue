<script setup lang="ts">
/** activity 热力图：ECharts calendar 坐标 + piecewise visualMap 着色。
 * 着色档位见 model/heatmap.ts；档位值直接编码进 data 第二维，由隐藏
 * visualMap 映射为颜色（heatmap 系列必须搭配 visualMap，缺了 dev 下会抛错）。
 * 格子保持方形：监听容器宽度，按"可用宽 / 列数"算出边长，组件高度随边长联动。
 */

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import {
  buildHeatmapOption,
  HEATMAP_LAYOUT,
  weekCount,
  type HeatValue,
} from '@/features/activity/model/heatmap-option'
import type { DayActivity } from '@/features/activity/types'

const props = defineProps<{
  daily: DayActivity[]
  selected: string | null
}>()

const emit = defineEmits<{
  select: [date: string]
}>()

const palette = useChartPalette()

/** 格子边长上下限：太宽留白多、太窄看不清 */
const MIN_CELL = 6
const MAX_CELL = 20
const FALLBACK_CELL = 14

const wrap = ref<HTMLElement | null>(null)
const wrapWidth = ref(0)
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!wrap.value) return
  wrapWidth.value = wrap.value.clientWidth
  observer = new ResizeObserver((entries) => {
    wrapWidth.value = entries[0]?.contentRect.width ?? 0
  })
  observer.observe(wrap.value)
})

onBeforeUnmount(() => observer?.disconnect())

const cellSize = computed(() => {
  if (!wrapWidth.value) return FALLBACK_CELL
  const usable = wrapWidth.value - HEATMAP_LAYOUT.left - HEATMAP_LAYOUT.right
  const cell = Math.floor(usable / weekCount(props.daily))
  return Math.min(MAX_CELL, Math.max(MIN_CELL, cell))
})

const heatmapHeight = computed(
  () => HEATMAP_LAYOUT.top + cellSize.value * 7 + HEATMAP_LAYOUT.bottom,
)

const option = computed(() =>
  buildHeatmapOption(props.daily, props.selected, palette.value, cellSize.value),
)

function onClick(params: unknown): void {
  const value = (params as { value?: HeatValue }).value
  if (value?.[0]) emit('select', value[0])
}
</script>

<template>
  <div ref="wrap" class="activity-heatmap" :style="{ height: `${heatmapHeight}px` }">
    <ChartHost v-if="daily.length" :option="option" @chart-click="onClick" />
    <div v-else class="heatmap-empty">该时间范围内暂无训练数据</div>
  </div>
</template>

<style scoped>
.activity-heatmap {
  min-height: 96px;
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
