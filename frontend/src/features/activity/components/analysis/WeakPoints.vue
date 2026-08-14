<script setup lang="ts">
/** 薄弱点列表：按技能域分组卡片，每条显示技能名、掌握度进度条（n-progress）、
 *  通过率 / 尝试 / AC 数与规则化建议文案。分组逻辑见 model/analysis.ts。 */

import { computed } from 'vue'
import { NProgress } from 'naive-ui'
import { buildWeakPointGroups, percentText } from '@/features/activity/model/analysis'
import type { WeakPoint } from '@/features/activity/types'

const props = defineProps<{
  weakPoints: WeakPoint[]
}>()

const groups = computed(() => buildWeakPointGroups(props.weakPoints))

function proficiencyPercent(w: WeakPoint): number {
  return Math.round(w.proficiency * 100)
}
</script>

<template>
  <div class="weak-points">
    <section v-for="group in groups" :key="group.domainKey" class="wp-group">
      <h4 class="wp-domain">{{ group.domainName }}</h4>
      <ul class="wp-list">
        <li v-for="w in group.items" :key="w.key" class="wp-item">
          <div class="wp-row">
            <span class="wp-name">{{ w.name }}</span>
            <span class="wp-meta mono">
              掌握 {{ percentText(w.proficiency) }} · 通过率 {{ percentText(w.passRate) }} ·
              {{ w.solvedCount }}/{{ w.attemptCount }} AC
            </span>
          </div>
          <NProgress
            type="line"
            :percentage="proficiencyPercent(w)"
            :height="6"
            :show-indicator="false"
            class="wp-progress"
          />
          <p class="wp-suggestion">{{ w.suggestion }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.weak-points {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wp-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wp-domain {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.wp-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.wp-item {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
}

.wp-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.wp-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.wp-meta {
  flex: none;
  font-size: 11px;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.wp-progress {
  margin-bottom: 6px;
}

.wp-suggestion {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.55;
}
</style>
