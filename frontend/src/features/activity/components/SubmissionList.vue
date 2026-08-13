<script setup lang="ts">
/** 左栏提交列表：默认近期提交（跨天合并，较新在上）；
 * 点击热力图格子后切换为当日明细（再次点击该格子取消选中）。
 * 两种模式均每页 10 条，底部分页导航；页码状态各自独立（见 store）。 */

import { computed } from 'vue'
import { ExternalLink, Inbox } from 'lucide-vue-next'
import { NPagination } from 'naive-ui'
import { parseDate, todayStr, weekdayCn } from '@/features/activity/model/dates'
import { pageCount, paged } from '@/features/activity/model/pagination'
import { useActivity } from '@/features/activity/store'
import type { RecentSubmission, SubmissionEntry, Verdict } from '@/features/activity/types'

const { platformName } = useActivity()

const props = defineProps<{
  /** 热力图选中的日期；null 表示近期提交模式 */
  selectedDate: string | null
  recent: RecentSubmission[]
  dayEntries: SubmissionEntry[]
  /** 当前模式的分页页码（从 1 起） */
  page: number
}>()

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const dayMode = computed(() => props.selectedDate !== null)

const totalPages = computed(() =>
  pageCount(dayMode.value ? props.dayEntries.length : props.recent.length),
)

const dateLabel = computed(() => {
  if (!props.selectedDate) return ''
  const d = parseDate(props.selectedDate)
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · 周${weekdayCn(props.selectedDate)}`
})

/** 当日通过的不同题目数 */
const solvedCount = computed(
  () => new Set(props.dayEntries.filter((e) => e.verdict === 'AC').map((e) => e.problemKey)).size,
)

interface Row {
  id: string
  platform: SubmissionEntry['platform']
  problemKey: string
  problemName: string
  problemUrl: string
  verdict: Verdict
  language: string
  timeLabel: string
}

const rows = computed<Row[]>(() => {
  if (dayMode.value) {
    return paged(props.dayEntries, props.page).map((e) => ({ ...e, timeLabel: e.time }))
  }
  const today = todayStr()
  return paged(props.recent, props.page).map((e) => ({
    ...e,
    // 今天的提交只显示时刻，更早的带上日期
    timeLabel: e.date === today ? e.time : `${e.date.slice(5)} ${e.time}`,
  }))
})

/** verdict 徽章固定配色：AC 绿 / WA 红 / CE 黄 / RE 紫 / JG 浅蓝 / 资源超限与未知深蓝 */
const VERDICT_CLASS: Record<Verdict, string> = {
  AC: 'v-ac',
  WA: 'v-wa',
  CE: 'v-ce',
  RE: 'v-re',
  JG: 'v-jg',
  TLE: 'v-limit',
  MLE: 'v-limit',
  OLE: 'v-limit',
  UKE: 'v-limit',
}

function openProblem(row: Row): void {
  window.open(row.problemUrl, '_blank', 'noopener')
}
</script>

<template>
  <div class="sub-list">
    <header class="list-head">
      <span class="list-title">{{ dayMode ? dateLabel : '近期提交' }}</span>
      <span v-if="dayMode" class="list-total mono">
        {{ dayEntries.length }} 次提交 · 通过 {{ solvedCount }} 题
      </span>
      <span v-else class="list-total mono">{{ recent.length }} 条</span>
    </header>

    <div v-if="rows.length" class="list-rows">
      <button
        v-for="row in rows"
        :key="row.id"
        type="button"
        class="sub-row"
        @click="openProblem(row)"
      >
        <span class="row-top">
          <span class="verdict mono" :class="VERDICT_CLASS[row.verdict]">{{ row.verdict }}</span>
          <span class="sub-problem">
            <span class="sub-platform">{{ platformName(row.platform) }}</span>
            <span class="sub-name">{{ row.problemKey }}. {{ row.problemName }}</span>
            <ExternalLink class="sub-link" :size="11" />
          </span>
        </span>
        <span class="row-bottom">
          <span class="sub-lang mono">{{ row.language }}</span>
          <span class="sub-time mono">{{ row.timeLabel }}</span>
        </span>
      </button>
    </div>
    <div v-else class="list-empty">
      <Inbox :size="20" />
      <span>{{ dayMode ? '这一天还没有提交记录' : '近期还没有提交记录' }}</span>
    </div>

    <footer v-if="totalPages > 1" class="list-foot">
      <!-- page-slot 7：默认 9 个槽位（1 2 3 4 5 6 7 … 末页）会溢出左栏宽度 -->
      <NPagination
        :page="page"
        :page-count="totalPages"
        :page-slot="7"
        size="small"
        @update:page="(p: number) => emit('update:page', p)"
      />
    </footer>
  </div>
</template>

<style scoped>
.sub-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.list-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  flex: none;
}

.list-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.list-total {
  margin-left: auto;
  font-size: 11px;
  color: var(--faint);
  white-space: nowrap;
}

.list-rows {
  flex: 1;
  margin: 0 -16px;
  padding: 0 16px;
}

.list-foot {
  display: flex;
  justify-content: center;
  padding-top: 10px;
  margin-top: auto;
  border-top: 1px solid var(--border);
  flex: none;
}

.sub-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 100%;
  padding: 8px 6px;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease;
}

.sub-row:last-child {
  border-bottom: 0;
}

.sub-row:hover {
  background: var(--surface-2);
}

.row-top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.row-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-left: 46px;
}

.verdict {
  display: inline-flex;
  justify-content: center;
  width: 38px;
  flex: none;
  padding: 1px 0;
  border-radius: 4px;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

/* verdict 徽章配色固定，不随主题色相与明暗变化 */
.v-ac {
  color: #1e9e52;
  background: hsl(142 60% 42% / 0.14);
}

.v-wa {
  color: #d64541;
  background: hsl(4 64% 52% / 0.12);
}

.v-ce {
  color: #c28a0a;
  background: hsl(42 88% 45% / 0.15);
}

.v-re {
  color: #8a5cf0;
  background: hsl(262 70% 60% / 0.14);
}

/* 评测中（CF 的 SUBMITTED / TESTING）：浅蓝 */
.v-jg {
  color: #2b8fc8;
  background: hsl(199 68% 55% / 0.15);
}

.v-limit {
  color: #2f5fc7;
  background: hsl(222 62% 50% / 0.13);
}

.sub-problem {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  font-size: 12.5px;
}

.sub-platform {
  flex: none;
  font-size: 11px;
  color: var(--faint);
}

.sub-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 550;
}

.sub-link {
  flex: none;
  align-self: center;
  color: var(--faint);
  opacity: 0;
  transition: opacity 0.15s ease;
}

.sub-row:hover .sub-link {
  opacity: 1;
}

.sub-lang {
  font-size: 11px;
  color: var(--faint);
}

.sub-time {
  font-size: 11px;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.list-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 26px 0;
  color: var(--faint);
  font-size: 12.5px;
}
</style>
