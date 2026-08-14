<script setup lang="ts">
/** 技能树 SVG 放射状可视化：根 → 技能域（第一环）→ 技能（第二环）。
 * 节点颜色 = accent 色按掌握度取透明度，大小随掌握度缩放；hover 出 tooltip。
 * 颜色全部来自主题桥接（useChartPalette），随明暗与色相联动。
 */

import { computed, ref } from 'vue'
import { useChartPalette } from '@/features/activity/components/use-chart-palette'
import { buildSkillTreeLayout, type RadialNode } from '@/features/activity/model/skill-tree'
import type { SkillTreeData } from '@/features/activity/types'

const props = defineProps<{
  data: SkillTreeData
}>()

const palette = useChartPalette()

/** 逻辑画布边长：SVG viewBox 固定，CSS 按容器宽度等比缩放 */
const SIZE = 840

const layout = computed(() => buildSkillTreeLayout(props.data, SIZE))

function pct(p: number): string {
  return `${Math.round(p * 100)}%`
}

/** 掌握度 → 填充透明度（最低仍留底可见，靠描边兜底） */
function fillOpacity(p: number): number {
  return 0.18 + 0.82 * p
}

/** 域 → 技能 的二次贝塞尔路径：控制点取中点向外偏移，形成扇形微弧 */
function domainToSkillPath(skill: (typeof layout.value.skills)[number]): string {
  const domain = layout.value.domains.find((d) => d.key === skill.domainKey)
  if (!domain) return ''
  const mx = (domain.pos.x + skill.pos.x) / 2
  const my = (domain.pos.y + skill.pos.y) / 2
  const cx = mx + (mx - layout.value.center.x) * 0.15
  const cy = my + (my - layout.value.center.y) * 0.15
  return `M ${domain.pos.x} ${domain.pos.y} Q ${cx} ${cy} ${skill.pos.x} ${skill.pos.y}`
}

/** 标签相对节点的横向锚点：节点在中心左侧则右对齐（text-anchor: end），反之左对齐 */
function labelAnchor(x: number): 'start' | 'end' {
  return x <= layout.value.center.x ? 'end' : 'start'
}

function labelDx(x: number, radius: number): number {
  return x <= layout.value.center.x ? -(radius + 8) : radius + 8
}

/* ---------- tooltip（跟随悬停节点） ---------- */

interface Tip {
  x: number
  y: number
  name: string
  acCount: number
  maxDifficulty: number | null
  proficiency: number
}

const tooltip = ref<Tip | null>(null)

function showTooltip(event: MouseEvent, node: RadialNode): void {
  const wrap = (event.currentTarget as SVGElement).ownerSVGElement?.parentElement
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  tooltip.value = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
    name: node.name,
    acCount: node.acCount,
    maxDifficulty: node.maxDifficulty,
    proficiency: node.proficiency,
  }
}

function hideTooltip(): void {
  tooltip.value = null
}
</script>

<template>
  <div class="skill-tree">
    <svg
      :viewBox="`0 0 ${SIZE} ${SIZE}`"
      role="img"
      aria-label="算法技能树"
    >
      <!-- 连线：根 → 域（直线） -->
      <g class="links">
        <line
          v-for="d in layout.domains"
          :key="`l-${d.key}`"
          :x1="layout.center.x"
          :y1="layout.center.y"
          :x2="d.pos.x"
          :y2="d.pos.y"
          :stroke="palette.faint"
          :stroke-opacity="0.3 + 0.5 * d.proficiency"
          stroke-width="1.5"
        />
        <!-- 连线：域 → 技能（曲线） -->
        <path
          v-for="s in layout.skills"
          :key="`p-${s.key}-${s.name}`"
          :d="domainToSkillPath(s)"
          :stroke="palette.faint"
          :stroke-opacity="0.2 + 0.45 * s.proficiency"
          stroke-width="1.2"
          fill="none"
        />
      </g>

      <!-- 技能域节点（第一环） -->
      <g
        v-for="(d, i) in layout.domains"
        :key="d.key"
        class="node"
        :style="{ animationDelay: `${0.1 + i * 0.05}s` }"
        @mouseenter="showTooltip($event, d)"
        @mouseleave="hideTooltip"
      >
        <circle
          :cx="d.pos.x"
          :cy="d.pos.y"
          :r="d.radius"
          :fill="palette.accent"
          :fill-opacity="fillOpacity(d.proficiency)"
          :stroke="palette.border"
          stroke-width="1.5"
        />
        <text
          :x="d.pos.x"
          :y="d.pos.y + d.radius + 16"
          text-anchor="middle"
          class="node-label"
          :fill="palette.text"
        >
          {{ d.name }}
        </text>
      </g>

      <!-- 技能节点（第二环） -->
      <g
        v-for="(s, i) in layout.skills"
        :key="`${s.domainKey}-${s.key}`"
        class="node"
        :style="{ animationDelay: `${0.3 + i * 0.03}s` }"
        @mouseenter="showTooltip($event, s)"
        @mouseleave="hideTooltip"
      >
        <circle
          :cx="s.pos.x"
          :cy="s.pos.y"
          :r="s.radius"
          :fill="palette.accent"
          :fill-opacity="fillOpacity(s.proficiency)"
          :stroke="palette.border"
          stroke-width="1"
        />
        <text
          :x="s.pos.x + labelDx(s.pos.x, s.radius)"
          :y="s.pos.y"
          :text-anchor="labelAnchor(s.pos.x)"
          dominant-baseline="central"
          class="skill-label"
          :fill="palette.text"
        >
          {{ s.name }}
        </text>
      </g>

      <!-- 根节点 -->
      <g class="node root-node">
        <circle
          :cx="layout.center.x"
          :cy="layout.center.y"
          :r="layout.root.radius"
          :fill="palette.accent"
          :stroke="palette.border"
          stroke-width="2"
        />
        <text
          :x="layout.center.x"
          :y="layout.center.y - 2"
          text-anchor="middle"
          class="root-title"
          :fill="palette.text"
        >
          技能树
        </text>
        <text
          :x="layout.center.x"
          :y="layout.center.y + 18"
          text-anchor="middle"
          class="root-pct"
          :fill="palette.text"
        >
          {{ pct(layout.root.proficiency) }}
        </text>
      </g>
    </svg>

    <!-- tooltip -->
    <Transition name="tooltip-fade">
      <div
        v-if="tooltip"
        class="skill-tooltip"
        :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
      >
        <div class="tip-name">{{ tooltip.name }}</div>
        <div class="tip-meta">
          AC {{ tooltip.acCount }} 题
          <template v-if="tooltip.maxDifficulty != null"> · 最高 {{ tooltip.maxDifficulty }}</template>
          · 掌握 {{ pct(tooltip.proficiency) }}
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.skill-tree {
  position: relative;
  width: 100%;
}

.skill-tree svg {
  display: block;
  width: 100%;
  height: auto;
}

/* 入场动效：节点由内向外 stagger 上浮淡入 */
.node {
  transform-box: fill-box;
  transform-origin: center;
  opacity: 0;
  animation: node-in 0.5s cubic-bezier(0.22, 0.8, 0.3, 1) forwards;
}

.node circle {
  transition:
    r 0.2s ease,
    fill-opacity 0.2s ease,
    stroke-width 0.2s ease;
  cursor: pointer;
}

.node:hover circle {
  stroke-width: 2.5;
}

.root-node {
  animation-delay: 0s;
}

.node-label {
  font-size: 14px;
  font-weight: 600;
  pointer-events: none;
}

.skill-label {
  font-size: 11.5px;
  pointer-events: none;
}

.root-title {
  font-size: 16px;
  font-weight: 700;
}

.root-pct {
  font-size: 12px;
  opacity: 0.85;
}

@keyframes node-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.7);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.skill-tooltip {
  position: absolute;
  z-index: 5;
  transform: translate(-50%, calc(-100% - 10px));
  padding: 6px 11px;
  border-radius: 8px;
  background: var(--text);
  color: var(--bg);
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
  transition: left 0.1s ease, top 0.1s ease;
}

.tip-name {
  font-weight: 600;
  margin-bottom: 2px;
}

.tip-meta {
  opacity: 0.85;
}

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.15s ease;
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
}
</style>
