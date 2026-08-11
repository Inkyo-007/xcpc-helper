<script setup lang="ts">
/** 当日提交明细：verdict 徽章 + 题目外链 + 平台/语言/时间元信息。 */

import { computed } from 'vue'
import { ExternalLink, Inbox } from 'lucide-vue-next'
import { parseDate, weekdayCn } from '@/features/activity/model/dates'
import { platformName } from '@/features/activity/model/mock'
import type { SubmissionEntry, Verdict } from '@/features/activity/types'

const props = defineProps<{
  date: string | null
  entries: SubmissionEntry[]
}>()

const dateLabel = computed(() => {
  if (!props.date) return ''
  const d = parseDate(props.date)
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · 周${weekdayCn(props.date)}`
})

/** 当日通过的不同题目数 */
const solvedCount = computed(
  () => new Set(props.entries.filter((e) => e.verdict === 'AC').map((e) => e.problemKey)).size,
)

const VERDICT_CLASS: Record<Verdict, string> = {
  AC: 'v-ac',
  WA: 'v-wa',
  TLE: 'v-tle',
  MLE: 'v-tle',
  RE: 'v-re',
}

function openProblem(entry: SubmissionEntry): void {
  window.open(entry.problemUrl, '_blank', 'noopener')
}
</script>

<template>
  <div class="submission-list">
    <div class="list-head">
      <span class="list-date">{{ dateLabel }}</span>
      <span class="list-total mono">{{ entries.length }} 次提交 · 通过 {{ solvedCount }} 题</span>
    </div>
    <div v-if="entries.length" class="list-rows">
      <button
        v-for="entry in entries"
        :key="entry.id"
        type="button"
        class="sub-row"
        @click="openProblem(entry)"
      >
        <span class="verdict mono" :class="VERDICT_CLASS[entry.verdict]">{{ entry.verdict }}</span>
        <span class="sub-problem">
          <span class="sub-name">{{ entry.problemName }}</span>
          <ExternalLink class="sub-link" :size="12" />
        </span>
        <span class="sub-platform">{{ platformName(entry.platform) }}</span>
        <span class="sub-lang mono">{{ entry.language }}</span>
        <span class="sub-time mono">{{ entry.time }}</span>
      </button>
    </div>
    <div v-else class="list-empty">
      <Inbox :size="22" />
      <span>这一天还没有提交记录</span>
    </div>
  </div>
</template>

<style scoped>
.submission-list {
  display: flex;
  flex-direction: column;
}

.list-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.list-date {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--text);
}

.list-total {
  font-size: 11.5px;
  color: var(--faint);
}

.list-rows {
  display: flex;
  flex-direction: column;
}

.sub-row {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) auto auto 44px;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  background: transparent;
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.sub-row:last-child {
  border-bottom: 0;
}

.sub-row:hover {
  background: var(--surface-2);
  transform: translateX(3px);
}

.verdict {
  display: inline-flex;
  justify-content: center;
  padding: 1px 0;
  border-radius: 4px;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.v-ac {
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.v-wa {
  color: #c63b57;
  background: hsl(350 60% 50% / 0.12);
}

.v-tle {
  color: #b97a1f;
  background: hsl(38 70% 45% / 0.14);
}

.v-re {
  color: var(--muted);
  background: var(--surface-2);
}

.sub-problem {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
  font-weight: 550;
}

.sub-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub-link {
  flex: none;
  color: var(--faint);
  opacity: 0;
  transition: opacity 0.15s ease;
}

.sub-row:hover .sub-link {
  opacity: 1;
}

.sub-platform {
  font-size: 11px;
  color: var(--muted);
  padding: 1px 8px;
  border: 1px solid var(--border);
  border-radius: 99px;
  white-space: nowrap;
}

.sub-lang {
  font-size: 11px;
  color: var(--faint);
  white-space: nowrap;
}

.sub-time {
  font-size: 11.5px;
  color: var(--muted);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 26px 0;
  color: var(--faint);
  font-size: 12.5px;
}
</style>
