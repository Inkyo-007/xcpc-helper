<script setup lang="ts">
/** activity 热力图：ECharts calendar 坐标 + piecewise visualMap 着色。
 * 着色档位见 model/heatmap.ts；档位值直接编码进 data 第二维，由隐藏
 * visualMap 映射为颜色（heatmap 系列必须搭配 visualMap，缺了 dev 下会抛错）。
 * 格子保持方形：监听容器宽度，按"可用宽 / 列数"算出边长并双向指定 cellSize，
 * 图表高度随边长联动；容器过窄时保持最小边长，改为横向滚动并默认停在
 * 右端（最近的日期一侧）。
 */

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import {
  buildHeatmapOption,
  HEATMAP_EDGE_PAD,
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
const scroller = ref<HTMLElement | null>(null)
const wrapWidth = ref(0)
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!wrap.value) return
  wrapWidth.value = wrap.value.clientWidth
  observer = new ResizeObserver((entries) => {
    wrapWidth.value = entries[0]?.contentRect.width ?? 0
  })
  observer.observe(wrap.value)
  void nextTick(pinToRightEdge)
})

onBeforeUnmount(() => observer?.disconnect())

const weeks = computed(() => weekCount(props.daily))

const cellSize = computed(() => {
  if (!wrapWidth.value) return FALLBACK_CELL
  const usable = wrapWidth.value - HEATMAP_LAYOUT.left - HEATMAP_EDGE_PAD.right
  const cell = Math.floor(usable / weeks.value)
  return Math.min(MAX_CELL, Math.max(MIN_CELL, cell))
})

/** 图表实际宽度：容器够宽则填满；过窄时保持最小边长对应宽度，由外层横向滚动 */
const chartWidth = computed(() => {
  const minWidth = HEATMAP_LAYOUT.left + MIN_CELL * weeks.value + HEATMAP_EDGE_PAD.right
  return Math.max(wrapWidth.value, minWidth)
})

const heatmapHeight = computed(
  () => HEATMAP_LAYOUT.top + cellSize.value * 7 + HEATMAP_EDGE_PAD.bottom,
)

const option = computed(() =>
  buildHeatmapOption(props.daily, props.selected, palette.value, cellSize.value),
)

/** 窄容器横向滚动时默认停在右端（最近的日期） */
function pinToRightEdge(): void {
  const el = scroller.value
  if (el) el.scrollLeft = el.scrollWidth
}

watch(chartWidth, () => void nextTick(pinToRightEdge))

function onClick(params: unknown): void {
  const value = (params as { value?: HeatValue }).value
  if (value?.[0]) emit('select', value[0])
}
</script>

<template>
  <div ref="wrap" class="activity-heatmap">
    <div ref="scroller" class="heatmap-scroll">
      <ChartHost
        v-if="daily.length"
        :style="{ width: `${chartWidth}px`, height: `${heatmapHeight}px` }"
        :option="option"
        @chart-click="onClick"
      />
      <div v-else class="heatmap-empty" :style="{ height: `${heatmapHeight}px` }">
        该时间范围内暂无训练数据
      </div>
    </div>
  </div>
</template>

<style scoped>
.activity-heatmap {
  min-height: 96px;
}

.heatmap-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}

.heatmap-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--faint);
}
</style>
