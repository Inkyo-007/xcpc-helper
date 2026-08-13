/** 训练统计数据 store（真实后端接入）。
 *
 * 账号与训练数据来自后端 data/user/default（第一期固定用户组）；
 * 用户组菜单仅影响档案（ID/签名/头像，见 profile.ts），不参与数据隔离。
 * 组件层只消费本模块暴露的状态与动作，接口名与样式原型阶段保持一致。
 */

import { computed, ref, watch } from 'vue'
import * as api from '@/features/activity/api'
import type {
  BoundAccount,
  DayActivity,
  OverviewTotals,
  PlatformId,
  PlatformMeta,
  RecentSubmission,
  SubmissionEntry,
} from '@/features/activity/types'

export type PlatformScope = 'all' | PlatformId

const accounts = ref<BoundAccount[]>([])
const platforms = ref<PlatformMeta[]>([])
const activePlatform = ref<PlatformScope>('all')
const selectedDate = ref<string | null>(null)
/** 近期提交列表的分页页码（从 1 起） */
const recentPage = ref(1)
/** 当日明细列表的分页页码（从 1 起；与近期提交各自独立，切换日期时重置） */
const dayPage = ref(1)
const syncing = ref(false)
const initialized = ref(false)

const overviewData = ref<api.ApiOverviewResponse | null>(null)
const recentItems = ref<RecentSubmission[]>([])
const dayItems = ref<SubmissionEntry[]>([])

const EMPTY_TOTALS: OverviewTotals = {
  totalSolved: 0,
  totalSubmissions: 0,
  todaySolved: 0,
  weekSolved: 0,
  streakDays: 0,
}

/** 当前平台视图（汇总或单平台）的日序列与总量（来自后端 overview） */
const mergedDaily = computed<DayActivity[]>(() => overviewData.value?.daily ?? [])
const totals = computed<OverviewTotals>(() => overviewData.value?.totals ?? EMPTY_TOTALS)
/** 当日明细（选中日期时） */
const entries = computed<SubmissionEntry[]>(() => dayItems.value)
/** 近期提交（未选中日期时），跨账号合并按时间倒序 */
const recentEntries = computed<RecentSubmission[]>(() => recentItems.value)

/* ---------- 数据加载（请求序号防竞态：快速切换时丢弃过期响应） ---------- */

let overviewReq = 0
let submissionsReq = 0

async function refreshOverview(): Promise<void> {
  const req = ++overviewReq
  try {
    const data = await api.fetchOverview(activePlatform.value)
    if (req === overviewReq) overviewData.value = data
  } catch {
    /* 请求失败保持旧数据；账号错误由 sync/status 呈现 */
  }
}

async function refreshSubmissions(): Promise<void> {
  const req = ++submissionsReq
  try {
    const data = await api.fetchSubmissions({
      date: selectedDate.value,
      platform: activePlatform.value,
    })
    if (req !== submissionsReq) return
    if (selectedDate.value) {
      dayItems.value = data.items
    } else {
      recentItems.value = data.items
    }
  } catch {
    /* 同上 */
  }
}

async function refreshAccounts(): Promise<void> {
  try {
    const res = await api.fetchPlatforms()
    platforms.value = res.platforms.map((p) => ({ id: p.id, name: p.name }))
    accounts.value = res.platforms
      .map((p) => p.account)
      .filter((a): a is BoundAccount => a !== null)
  } catch {
    /* 后端未就绪时保持空列表 */
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([refreshAccounts(), refreshOverview(), refreshSubmissions()])
}

/** 轮询同步状态直到全部账号不再同步中（失败亦视为结束） */
async function pollUntilIdle(timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const statuses = await api.fetchSyncStatus()
    if (statuses.every((s) => s.syncState !== 'running')) return
    await new Promise((r) => setTimeout(r, 300))
  }
}

/* ---------- 视图状态（网址恢复由 ActivityPage 驱动） ---------- */

function init(): void {
  if (initialized.value) return
  initialized.value = true
  void refreshAll()
}

function setPlatform(scope: PlatformScope): void {
  activePlatform.value = scope
  selectedDate.value = null
  recentPage.value = 1
  dayPage.value = 1
}

/** 直接设置选中日期（网址恢复用）；切换日期时当日明细页码回到第 1 页 */
function setSelectedDate(date: string | null): void {
  selectedDate.value = date
  dayPage.value = 1
}

/** 选中某天查看当日明细；再次点击同一格子取消选中，回到近期提交 */
function selectDate(date: string): void {
  setSelectedDate(selectedDate.value === date ? null : date)
}

/** 当前列表（近期提交或当日明细）的页码：随模式路由到对应状态 */
const listPage = computed({
  get: () => (selectedDate.value ? dayPage.value : recentPage.value),
  set: (page: number) => {
    if (selectedDate.value) dayPage.value = page
    else recentPage.value = page
  },
})

function setListPage(page: number): void {
  listPage.value = page
}

/* ---------- 动作 ---------- */

/** 立即同步全部账号（或当前平台视图的账号），完成后刷新数据 */
async function syncNow(): Promise<void> {
  if (syncing.value) return
  syncing.value = true
  try {
    await api.triggerSync(activePlatform.value === 'all' ? undefined : activePlatform.value)
    await pollUntilIdle()
    await refreshAll()
  } finally {
    syncing.value = false
  }
}

/** 绑定（或换绑）账号：后端自动触发首次同步，等待完成后刷新数据 */
async function bindAccount(platform: PlatformId, handle: string): Promise<void> {
  await api.bindAccount(platform, handle)
  await pollUntilIdle()
  await refreshAll()
}

/** 解绑并删除该账号本地数据 */
async function unbindAccount(platform: PlatformId, handle: string): Promise<void> {
  await api.unbindAccount(platform, handle)
  selectedDate.value = null
  await refreshAll()
}

/** 当前平台绑定的账号（每平台至多一个） */
function boundOn(platform: PlatformId): BoundAccount | null {
  return accounts.value.find((a) => a.platform === platform) ?? null
}

/** 判断 handle 是否已被绑定（绑定弹窗防重复用） */
function isBound(platform: PlatformId, handle: string): boolean {
  return accounts.value.some((a) => a.platform === platform && a.handle === handle)
}

function platformName(id: PlatformId): string {
  return platforms.value.find((p) => p.id === id)?.name ?? id
}

const lastSyncLabel = computed(() => {
  const times = accounts.value
    .map((a) => a.lastSyncAt)
    .filter((t): t is string => t !== null)
    .sort()
  if (times.length === 0) return '尚未同步'
  const minutes = Math.max(0, Math.round((Date.now() - Date.parse(times[0])) / 60000))
  if (minutes < 1) return '刚刚同步'
  if (minutes < 60) return `${minutes} 分钟前同步`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前同步`
  return `${Math.floor(hours / 24)} 天前同步`
})

/* 视图状态变化时重新拉取数据（防竞态见 refreshOverview/refreshSubmissions） */
watch([activePlatform, selectedDate], () => {
  void refreshOverview()
  void refreshSubmissions()
})

export function useActivity() {
  return {
    accounts,
    platforms,
    activePlatform,
    selectedDate,
    listPage,
    syncing,
    initialized,
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
    isBound,
    platformName,
  }
}
