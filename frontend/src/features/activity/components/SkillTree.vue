<script setup lang="ts">
/** 技能树旭日图（ECharts sunburst）：根 → 技能域 → 技能。
 * 扇区面积 ∝ 做题数，颜色按域取分类色相、掌握度驱动明度；悬停出 tooltip、
 * 高亮子树，点击领域下钻、点击中心返回。颜色全部来自主题桥接（useChartPalette），
 * 随明暗与色相联动。图例与图表用同一套色相（model/skill-tree.ts 的 buildDomainLegend）。
 */

import { computed } from 'vue'
import ChartHost from '@/features/activity/components/ChartHost.vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import {
  buildDomainLegend,
  buildSunburstOption,
} from '@/features/activity/model/skill-tree'
import type { SkillTreeData } from '@/features/activity/types'

const props = defineProps<{
  data: SkillTreeData
}>()

const palette = useChartPalette()

const option = computed(() => buildSunburstOption(props.data, palette.value))
const legend = computed(() => buildDomainLegend(props.data, palette.value))

function pct(p: number): string {
  return `${Math.round(p * 100)}%`
}
</script>

<template>
  <div class="skill-tree">
    <div class="st-chart">
      <ChartHost :option="option" />
    </div>

    <ul class="st-legend" aria-label="技能域图例">
      <li v-for="item in legend" :key="item.key" class="legend-chip">
        <i class="legend-dot" :style="{ background: item.color }"></i>
        <span class="legend-name">{{ item.name }}</span>
        <span class="legend-meta">{{ item.acCount }} 题 · {{ pct(item.proficiency) }}</span>
      </li>
    </ul>

    <p class="st-hint">悬停查看详情 · 点击领域放大查看技能，点击中心返回</p>
  </div>
</template>

<style scoped>
.skill-tree {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.st-chart {
  width: 100%;
  height: clamp(400px, 62vh, 640px);
}

.st-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-2);
}

.legend-dot {
  width: 10px;
  height: 10px;
  flex: none;
  border-radius: 50%;
}

.legend-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
}

.legend-meta {
  font-size: 11px;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}

.st-hint {
  margin: 0;
  font-size: 12px;
  color: var(--faint);
  text-align: center;
}
</style>
