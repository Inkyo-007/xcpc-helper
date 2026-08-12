<script setup lang="ts">
/** 统计卡片行：总解题 / 总提交 / 今日 / 连续天数，数字 count-up + 错峰入场。 */

import { onBeforeUnmount, ref, watch, type Component } from 'vue'
import { CalendarCheck2, CheckCircle2, Flame, Send } from 'lucide-vue-next'
import type { OverviewTotals } from '@/features/activity/types'

const props = defineProps<{
  totals: OverviewTotals
}>()

function useCountUp(target: () => number) {
  const display = ref('0')
  let raf = 0
  watch(
    target,
    (to) => {
      cancelAnimationFrame(raf)
      const from = Number(display.value.replace(/,/g, '')) || 0
      const start = performance.now()
      const duration = 650
      const tick = (now: number): void => {
        const p = Math.min(1, (now - start) / duration)
        const eased = 1 - Math.pow(1 - p, 3)
        display.value = Math.round(from + (to - from) * eased).toLocaleString('en-US')
        if (p < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    },
    { immediate: true },
  )
  onBeforeUnmount(() => cancelAnimationFrame(raf))
  return display
}

interface CardDef {
  key: string
  label: string
  icon: Component
  value: ReturnType<typeof useCountUp>
}

const cards: CardDef[] = [
  { key: 'solved', label: '总解题数', icon: CheckCircle2, value: useCountUp(() => props.totals.totalSolved) },
  { key: 'subs', label: '总提交数', icon: Send, value: useCountUp(() => props.totals.totalSubmissions) },
  { key: 'today', label: '今日解题', icon: CalendarCheck2, value: useCountUp(() => props.totals.todaySolved) },
  { key: 'streak', label: '连续天数', icon: Flame, value: useCountUp(() => props.totals.streakDays) },
]
</script>

<template>
  <div class="stat-cards">
    <div
      v-for="(card, i) in cards"
      :key="card.key"
      class="stat-card"
      :class="{ streak: card.key === 'streak' }"
      :style="{ animationDelay: `${i * 55}ms` }"
    >
      <span class="stat-icon">
        <component :is="card.icon" :size="16" :stroke-width="2.2" />
      </span>
      <div class="stat-body">
        <div class="stat-value mono">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  animation: card-in 0.4s cubic-bezier(0.22, 0.8, 0.3, 1) both;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  box-shadow: 0 6px 18px rgb(35 30 20 / 0.08);
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: var(--radius-sm);
  background: var(--accent-softer);
  color: var(--accent-strong);
}

.stat-card.streak .stat-icon {
  background: var(--accent-soft);
  color: var(--accent);
}

.stat-body {
  min-width: 0;
}

.stat-value {
  font-size: 21px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  margin-top: 1px;
  font-size: 11.5px;
  color: var(--faint);
}

@media (max-width: 720px) {
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
