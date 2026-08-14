<script setup lang="ts">
/** 数据总览页：左右双栏布局（无分界线）。
 * 左栏：用户信息卡 + 近期提交；右栏：统计卡片 + 训练热力图 + 通过数柱状图。 */

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChartColumn, MousePointerClick, Plus } from 'lucide-vue-next'
import { NButton, useMessage } from 'naive-ui'
import AccountBindModal from '@/features/activity/components/AccountBindModal.vue'
import ActivityHeatmap from '@/features/activity/components/ActivityHeatmap.vue'
import PassBarChart from '@/features/activity/components/PassBarChart.vue'
import PlatformTabs from '@/features/activity/components/PlatformTabs.vue'
import StatCards from '@/features/activity/components/StatCards.vue'
import SubmissionList from '@/features/activity/components/SubmissionList.vue'
import SyncBar from '@/features/activity/components/SyncBar.vue'
import SyncOverlay from '@/features/activity/components/SyncOverlay.vue'
import UserGroupEditModal from '@/features/activity/components/UserGroupEditModal.vue'
import UserProfileCard from '@/features/activity/components/UserProfileCard.vue'
import { monthlySolved, weeklySolved } from '@/features/activity/model/bars'
import { parseDate, toDateStr } from '@/features/activity/model/dates'
import { pageCount } from '@/features/activity/model/pagination'
import { useActivity, type PlatformScope } from '@/features/activity/store'
import type { AccountCredentials, PlatformId } from '@/features/activity/types'

const {
  accounts,
  activePlatform,
  selectedDate,
  listPage,
  syncing,
  busy,
  mergedDaily,
  totals,
  entries,
  recentEntries,
  lastSyncLabel,
  init,
  setPlatform,
  selectDate,
  setSelectedDate,
  setListPage,
  syncNow,
  bindAccount,
  unbindAccount,
  boundOn,
} = useActivity()

const message = useMessage()
const showBind = ref(false)
/** 绑定弹窗锁定的平台：从平台视图的账号按钮打开时为该平台，空状态入口为 null */
const bindPreset = ref<PlatformId | null>(null)
/** 编辑用户组弹窗（重命名 / 删除 / 换绑账号） */
const showGroupEdit = ref(false)

const weeklyBars = computed(() => weeklySolved(mergedDaily.value))
const monthlyBars = computed(() => monthlySolved(mergedDaily.value))

/* ---------- 网址状态同步：?platform=<平台>&date=<日期>&page=<页码> ----------
 * all、无选中日期与第 1 页为缺省值，不出现在网址中；切换平台重置日期
 * 与页码，选中日期切换当日明细时页码回到第 1 页（见 store）；
 * 刷新、浏览器前进/后退与复制链接均能恢复同一视图。 */

const route = useRoute()
const router = useRouter()

const PLATFORM_SCOPES: PlatformScope[] = [
  'all',
  'codeforces',
  'atcoder',
  'luogu',
  'leetcode-cn',
  'nowcoder',
]

/** 网址中的平台筛选：非法值回退为汇总（平台页签与绑定状态无关） */
function queryPlatform(raw: unknown): PlatformScope {
  if (typeof raw !== 'string' || raw === 'all') return 'all'
  if (!(PLATFORM_SCOPES as string[]).includes(raw)) return 'all'
  return raw as PlatformScope
}

/** 网址中的页码：非正整数回退为第 1 页 */
function queryPage(raw: unknown): number {
  const n = Number(typeof raw === 'string' ? raw : '')
  return Number.isInteger(n) && n > 0 ? n : 1
}

/** 网址中的选中日期：非法格式或不存在的日期回退为未选中 */
function queryDate(raw: unknown): string | null {
  if (typeof raw !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null
  // parseDate 会把 2 月 31 日之类的日期顺延，回写比对即可识别
  return toDateStr(parseDate(raw)) === raw ? raw : null
}

onMounted(() => {
  init()
  // 从网址恢复视图（顺序固定：平台 → 日期 → 页码：
  // 切平台会重置日期与页码，切日期会把当日明细页码重置回 1）
  const platform = queryPlatform(route.query.platform)
  if (platform !== 'all') setPlatform(platform)
  const date = queryDate(route.query.date)
  if (date) setSelectedDate(date)
  const page = queryPage(route.query.page)
  if (page > 1) setListPage(page)
})

// 状态 → 网址：缺省值不写入，避免无谓的跳转
watch([activePlatform, selectedDate, listPage], ([platform, date, page]) => {
  const query: Record<string, string> = {}
  if (platform !== 'all') query.platform = platform
  if (date) query.date = date
  if (page > 1) query.page = String(page)
  if (
    query.platform === route.query.platform &&
    query.date === route.query.date &&
    query.page === route.query.page
  ) {
    return
  }
  void router.push({ query })
})

// 网址 → 状态：浏览器前进/后退（或手动改网址）时恢复视图
watch(
  () => route.query,
  (query) => {
    const platform = queryPlatform(query.platform)
    if (platform !== activePlatform.value) setPlatform(platform)
    const date = queryDate(query.date)
    if (date !== selectedDate.value) setSelectedDate(date)
    const page = queryPage(query.page)
    if (page !== listPage.value) setListPage(page)
  },
)

// 当前列表（近期提交或当日明细）变短导致页码超出范围时夹紧
watch(
  () => (selectedDate.value ? entries.value.length : recentEntries.value.length),
  (total) => {
    const max = pageCount(total)
    if (listPage.value > max) setListPage(max)
  },
)

/** 打开绑定弹窗：platform 为 null 时自由选择平台（空状态入口） */
function openBind(platform: PlatformId | null): void {
  bindPreset.value = platform
  showBind.value = true
}

async function onBind(
  platform: PlatformId,
  handle: string,
  opts: { displayName?: string | null; credentials?: AccountCredentials } = {},
): Promise<void> {
  const rebinding = boundOn(platform) !== null
  try {
    await bindAccount(platform, handle, opts)
    message.success(rebinding ? '换绑成功，已重新同步' : '绑定成功，已完成首次同步')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '绑定失败，请稍后重试')
  }
}

async function onUnbind(platform: PlatformId, handle: string): Promise<void> {
  try {
    await unbindAccount(platform, handle)
    message.success('已解绑并删除本地数据')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '解绑失败，请稍后重试')
  }
}
</script>

<template>
  <div class="act-page">
    <div class="act-toolbar">
      <PlatformTabs
        :model-value="activePlatform"
        @update:model-value="setPlatform"
      />
      <SyncBar
        :last-sync-label="lastSyncLabel"
        :syncing="syncing"
        :accounts="accounts"
        :active-platform="activePlatform"
        @sync="syncNow"
        @bind="openBind"
        @edit-group="showGroupEdit = true"
      />
    </div>

    <div v-if="accounts.length" class="act-body">
      <aside class="act-side">
        <UserProfileCard />
        <section class="act-panel act-submissions">
          <SubmissionList
            :selected-date="selectedDate"
            :recent="recentEntries"
            :day-entries="entries"
            :page="listPage"
            @update:page="setListPage"
          />
        </section>
      </aside>

      <div class="act-main">
        <StatCards :totals="totals" />

        <section class="act-panel">
          <header class="panel-head">
            <span class="panel-title">训练热力</span>
            <span class="panel-hint">
              <MousePointerClick :size="12" />
              点击格子查看当日明细，再次点击取消
            </span>
            <span class="heat-legend">
              少
              <i class="legend-cell lv0"></i>
              <i class="legend-cell lv1"></i>
              <i class="legend-cell lv2"></i>
              <i class="legend-cell lv3"></i>
              <i class="legend-cell lv4"></i>
              <i class="legend-cell lv5"></i>
              多
            </span>
          </header>
          <ActivityHeatmap :daily="mergedDaily" :selected="selectedDate" @select="selectDate" />
        </section>

        <div class="act-charts">
          <section class="act-panel">
            <header class="panel-head">
              <span class="panel-title">近 7 天通过</span>
            </header>
            <PassBarChart :data="weeklyBars" />
          </section>
          <section class="act-panel">
            <header class="panel-head">
              <span class="panel-title">近 12 个月通过</span>
            </header>
            <PassBarChart :data="monthlyBars" />
          </section>
        </div>
      </div>
    </div>

    <div v-else class="act-empty">
      <div class="empty-icon">
        <ChartColumn :size="26" />
      </div>
      <h2 class="empty-title">还没有训练数据</h2>
      <p class="empty-hint">绑定一个竞赛平台账号，同步后这里会展示你的训练统计。</p>
      <NButton type="primary" @click="openBind(null)">
        <template #icon><Plus :size="15" /></template>
        绑定第一个账号
      </NButton>
    </div>

    <AccountBindModal v-model:show="showBind" :platform="bindPreset" @bind="onBind" />
    <UserGroupEditModal
      v-model:show="showGroupEdit"
      :accounts="accounts"
      @bind="openBind"
      @unbind="onUnbind"
    />
    <SyncOverlay :show="busy" />
  </div>
</template>

<style scoped>
.act-page {
  flex: 1;
  min-height: 0;
  /* 整页滚动：近期提交等内容较多时由页面承担滚动，不再用内部滚动区 */
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 20px 16px;
}

.act-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
}

/* 左右双栏：仅以间距区分，不画分界线 */
.act-body {
  flex: 1;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
}

.act-side {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.act-submissions {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.act-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.act-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.act-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 12px 16px 10px;
  flex: none;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.panel-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.panel-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--faint);
}

.heat-legend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
  font-size: 11px;
  color: var(--faint);
}

.legend-cell {
  width: 11px;
  height: 11px;
  border-radius: 3px;
}

.legend-cell.lv0 {
  background: var(--surface-2);
  border: 1px solid var(--border);
}

.legend-cell.lv1 {
  background: hsl(var(--hue) 68% 48% / 0.16);
}

.legend-cell.lv2 {
  background: hsl(var(--hue) 68% 48% / 0.42);
}

.legend-cell.lv3 {
  background: hsl(var(--hue) 68% 48% / 0.62);
}

.legend-cell.lv4 {
  background: hsl(var(--hue) 68% 48% / 0.82);
}

.legend-cell.lv5 {
  background: hsl(var(--hue) 68% 48% / 1);
}

.act-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--faint);
  text-align: center;
  padding: 40px;
}

.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  height: 60px;
  margin-bottom: 6px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--accent);
}

.empty-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.empty-hint {
  margin: 0 0 6px;
  max-width: 340px;
  font-size: 12.5px;
}

@media (max-width: 1080px) {
  .act-body {
    flex: none;
    grid-template-columns: 1fr;
  }

  .act-side {
    min-height: auto;
  }
}

@media (max-width: 900px) {
  .act-charts {
    grid-template-columns: 1fr;
  }
}

.act-page::-webkit-scrollbar {
  width: 10px;
}

.act-page::-webkit-scrollbar-thumb {
  background: var(--accent);
  border-radius: 99px;
  border: 3px solid transparent;
  background-clip: content-box;
}
</style>
