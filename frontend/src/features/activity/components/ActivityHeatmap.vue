<script setup lang="ts">
/** activity 热力图：DOM 网格（列 = 周，周日起始；数据展开见 model/heatmap-grid.ts）。
 * 悬停格子上浮（放大 + 投影 + z-index 置顶，不被相邻格遮挡）；点击选中后
 * 该格维持上浮并加 accent 描边，其余格子淡化且不再响应悬停动效。
 * 格子保持方形：监听容器宽度，按"可用宽 / 列数"算出边长；容器过窄时保持
 * 最小边长，改为横向滚动并默认停在右端（最近的日期一侧）。
 * 格子颜色复用主题桥接的配色对象（model/echarts-theme.ts），随明暗与色相联动。
 */

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import {
  buildHeatmapCells,
  buildMonthLabels,
  weekCount,
  type HeatCell,
} from '@/features/activity/model/heatmap-grid'
import type { DayActivity } from '@/features/activity/types'

const props = defineProps<{
  daily: DayActivity[]
  selected: string | null
}>()

const emit = defineEmits<{
  select: [date: string]
}>()

const palette = useChartPalette()

/** 格子边长上下限与格间距：太宽留白多、太窄看不清 */
const MIN_CELL = 9
const MAX_CELL = 16
const FALLBACK_CELL = 12
const GAP = 3
/** 左侧星期标签列宽与右侧预留空白 */
const LABEL_W = 26
const PAD_RIGHT = 12
/** 月份标签行高与下方间距 */
const MONTH_ROW_H = 20

/** 周日起始网格的行标签：只标 一/三/五 三行，小格子下 7 行标签会互相挤压 */
const DAY_LABELS = ['', '一', '', '三', '', '五', '']

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
const cells = computed(() => buildHeatmapCells(props.daily))
const monthLabels = computed(() => buildMonthLabels(cells.value))

const cellSize = computed(() => {
  if (!wrapWidth.value) return FALLBACK_CELL
  const usable = wrapWidth.value - LABEL_W - PAD_RIGHT - GAP * (weeks.value - 1)
  const cell = Math.floor(usable / weeks.value)
  return Math.min(MAX_CELL, Math.max(MIN_CELL, cell))
})

/** 图表实际宽度：容器够宽则填满；过窄时保持最小边长对应宽度，由外层横向滚动 */
const chartWidth = computed(() => {
  const minWidth = LABEL_W + MIN_CELL * weeks.value + GAP * (weeks.value - 1) + PAD_RIGHT
  return Math.max(wrapWidth.value, minWidth)
})

const gridHeight = computed(() => cellSize.value * 7 + GAP * 6)
const heatmapHeight = computed(() => MONTH_ROW_H + gridHeight.value + 4)

const columnsStyle = computed(() => ({
  gridTemplateColumns: `repeat(${weeks.value}, ${cellSize.value}px)`,
  gap: `${GAP}px`,
}))

const gridStyle = computed(() => ({
  ...columnsStyle.value,
  gridTemplateRows: `repeat(7, ${cellSize.value}px)`,
  gridAutoFlow: 'column' as const,
}))

/** 窄容器横向滚动时默认停在右端（最近的日期） */
function pinToRightEdge(): void {
  const el = scroller.value
  if (el) el.scrollLeft = el.scrollWidth
}

watch(chartWidth, () => void nextTick(pinToRightEdge))

function cellColor(level: number): string {
  return palette.value.heatColors[level]
}

/** 单个跟随悬停格子的 tooltip（370 格各挂一个 NTooltip 太重，改用一个浮层） */
const tooltip = ref<{ x: number; y: number; text: string } | null>(null)

function onCellEnter(event: MouseEvent, cell: HeatCell): void {
  // 选中态下其余格子不响应悬停（动效由 CSS 禁用，tooltip 在此同步禁用）
  if (props.selected !== null && cell.date !== props.selected) return
  const wrapRect = wrap.value?.getBoundingClientRect()
  if (!wrapRect) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  // 水平方向夹紧，避免边缘格子的 tooltip 溢出容器
  const x = Math.min(
    Math.max(rect.left - wrapRect.left + rect.width / 2, 90),
    Math.max(wrapRect.width - 90, 90),
  )
  tooltip.value = {
    x,
    y: rect.top - wrapRect.top,
    text: `${cell.date} · 提交 ${cell.submissions} 次 · 通过 ${cell.solved} 题`,
  }
}

function hideTooltip(): void {
  tooltip.value = null
}

// 选中切换 / 数据刷新后，悬停中的格子可能变为禁用态或位移，直接收起 tooltip
watch(() => props.selected, hideTooltip)
watch(cells, hideTooltip)

function onCellClick(cell: HeatCell): void {
  emit('select', cell.date)
}
</script>

<template>
  <div ref="wrap" class="activity-heatmap">
    <div ref="scroller" class="heatmap-scroll" @scroll.passive="hideTooltip">
      <div
        v-if="daily.length"
        class="heatmap-inner"
        :style="{ width: `${chartWidth}px`, height: `${heatmapHeight}px` }"
      >
        <div class="month-row" :style="columnsStyle">
          <span
            v-for="m in monthLabels"
            :key="m.week"
            class="month-label"
            :style="{ gridColumnStart: m.week + 1 }"
          >
            {{ m.label }}
          </span>
        </div>
        <div class="heatmap-body">
          <div class="day-labels" :style="{ gridTemplateRows: `repeat(7, ${cellSize}px)`, gap: `${GAP}px` }">
            <span v-for="(label, i) in DAY_LABELS" :key="i" class="day-label">{{ label }}</span>
          </div>
          <div class="heatmap-grid" :class="{ 'has-selection': selected !== null }" :style="gridStyle">
            <template v-for="(cell, i) in cells" :key="i">
              <span v-if="cell === null" class="heat-blank"></span>
              <button
                v-else
                type="button"
                class="heat-cell"
                :class="{ selected: cell.date === selected }"
                :style="{ background: cellColor(cell.level) }"
                :aria-label="`${cell.date}，提交 ${cell.submissions} 次，通过 ${cell.solved} 题`"
                :aria-pressed="cell.date === selected"
                @click="onCellClick(cell)"
                @mouseenter="onCellEnter($event, cell)"
                @mouseleave="hideTooltip"
              ></button>
            </template>
          </div>
        </div>
      </div>
      <div v-else class="heatmap-empty" :style="{ height: `${heatmapHeight}px` }">
        该时间范围内暂无训练数据
      </div>
    </div>
    <div v-if="tooltip" class="heat-tooltip" :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }">
      {{ tooltip.text }}
    </div>
  </div>
</template>

<style scoped>
.activity-heatmap {
  position: relative;
  min-height: 96px;
}

.heatmap-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}

.month-row {
  display: grid;
  height: 14px;
  margin: 0 v-bind('PAD_RIGHT + "px"') 6px v-bind('LABEL_W + "px"');
}

.month-label {
  font-size: 11px;
  line-height: 14px;
  color: var(--faint);
  white-space: nowrap;
}

.heatmap-body {
  display: flex;
  gap: v-bind('GAP + "px"');
}

.day-labels {
  display: grid;
  width: v-bind('LABEL_W - GAP + "px"');
  flex: none;
}

.day-label {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  font-size: 10px;
  color: var(--faint);
}

.heatmap-grid {
  display: grid;
}

.heat-cell {
  position: relative;
  padding: 0;
  border: 0;
  border-radius: 3px;
  cursor: pointer;
  transition:
    transform 0.18s cubic-bezier(0.22, 0.8, 0.3, 1),
    box-shadow 0.18s ease,
    opacity 0.18s ease;
}

/* 悬停上浮：放大 + 投影 + 置顶，盖住相邻格子 */
.heat-cell:hover {
  z-index: 3;
  transform: translateY(-2px) scale(1.25);
  box-shadow: 0 5px 12px rgb(20 16 10 / 0.3);
}

/* 选中格维持上浮态，加 accent 描边 */
.heat-cell.selected {
  z-index: 3;
  transform: translateY(-2px) scale(1.25);
  box-shadow:
    0 5px 12px rgb(20 16 10 / 0.3),
    0 0 0 1.5px var(--accent);
}

/* 有选中格时其余格子淡化，且不再响应悬停动效（仍可点击以切换选中） */
.heatmap-grid.has-selection .heat-cell:not(.selected) {
  opacity: 0.28;
}

.heatmap-grid.has-selection .heat-cell:not(.selected):hover {
  z-index: auto;
  transform: none;
  box-shadow: none;
}

.heat-tooltip {
  position: absolute;
  z-index: 5;
  transform: translate(-50%, calc(-100% - 7px));
  padding: 5px 10px;
  border-radius: 6px;
  background: var(--text);
  color: var(--bg);
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
}

.heatmap-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--faint);
}
</style>
