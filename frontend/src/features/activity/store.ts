/** 训练统计数据 store（真实后端接入）。
 *
 * 账号与训练数据来自后端当前用户组目录（data/user/<user_id>/）；
 * 切组（currentKey 变化）后重新拉取该组数据，组件层无感知。
 */

import { computed, ref, watch } from 'vue'
import * as api from '@/features/activity/api'
import { useUserGroups } from '@/features/activity/profile'
import type {
  AccountCredentials,
  BoundAccount,
  DayActivity,
  OverviewTotals,
  PlatformId,
  PlatformMeta,
  RecentSubmission,
  SubmissionEntry,
} from '@/features/activity/types'

export type PlatformScope = 'all' | PlatformId

const { currentKey, ensureLoaded } = useUserGroups()

const accounts = ref<BoundAccount[]>([])
const platforms = ref<PlatformMeta[]>([])
const activePlatform = ref<PlatformScope>('all')
const selectedDate = ref<string | null>(null)
/** 近期提交列表的分页页码（从 1 起） */
const recentPage = ref(1)
/** 当日明细列表的分页页码（从 1 起；与近期提交各自独立，切换日期时重置） */
const dayPage = ref(1)
/** 任一账号同步中或刚触发（驱动同步按钮转圈 / 平台页签角标 / 平台视图进度面板；
 * 同步为纯后台属性，不再有全局遮罩）。syncFiring 覆盖"刚点击、首轮状态尚未
 * 合并"的窗口期，让快速完成的同步也有即时反馈。 */
const syncFiring = ref(false)
const syncing = computed(
  () => syncFiring.value || accounts.value.some((a) => a.syncState === 'running'),
)
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
    platforms.value = res.platforms.map((p) => ({
      id: p.id,
      name: p.name,
      auth: p.auth,
      browserLogin: p.browserLogin,
      capabilities: p.capabilities,
    }))
    accounts.value = res.platforms
      .map((p) => p.account)
      .filter((a): a is BoundAccount => a !== null)
    // 发现页面加载前已在运行的精化（黄点角标），并在跑完前保持跟踪
    void refreshRefineStates().then(() => {
      if (refiningKeys.value.length > 0) pollRefineInBackground()
    })
  } catch {
    /* 后端未就绪时保持空列表 */
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([refreshAccounts(), refreshOverview(), refreshSubmissions()])
}

/** 把 /sync/status 的运行态合并进 accounts（同步中/进度/错误实时可见） */
function mergeSyncStatuses(statuses: BoundAccount[]): void {
  for (const s of statuses) {
    const acc = accounts.value.find(
      (a) => a.platform === s.platform && a.handle === s.handle,
    )
    if (acc) Object.assign(acc, s)
    else accounts.value.push(s)
  }
}

/** 轮询同步状态（首 tick 较快 300ms，让快速完成的同步也呈现进行态），
 * 实时合并到 accounts，全部完成后刷新数据并返回最终状态列表。 */
async function watchSyncUntilIdle(): Promise<BoundAccount[]> {
  let statuses: BoundAccount[] = []
  await new Promise((r) => setTimeout(r, 300))
  while (true) {
    statuses = await api.fetchSyncStatus()
    mergeSyncStatuses(statuses)
    if (statuses.every((s) => s.syncState !== 'running')) break
    await new Promise((r) => setTimeout(r, 2000))
  }
  await refreshAll()
  return statuses
}

/** 后台低频轮询（fire-and-forget，用于绑定后/发现在途同步等非手动场景） */
let bgPolling = false
function pollInBackground(): void {
  if (bgPolling) return
  bgPolling = true
  void (async () => {
    try {
      await watchSyncUntilIdle()
    } catch {
      /* 后端不可达时静默结束，下次操作再拉 */
    } finally {
      bgPolling = false
    }
  })()
}

/* ---------- 精细化同步运行态（驱动精化按钮黄点角标） ---------- */

/** 正在精化的账号键集合（"platform/handle"） */
export const refiningKeys = ref<string[]>([])

function refineKey(platform: string, handle: string): string {
  return `${platform}/${handle}`
}

/** 拉取精化能力账号的运行态，维护 refiningKeys（启动时调用一次发现
 * 页面加载前已在运行的精化；之后靠 poller 跟踪到结束） */
async function refreshRefineStates(): Promise<void> {
  const targets = accounts.value.filter((a) =>
    platformMeta(a.platform)?.capabilities.includes('refine_verdict'),
  )
  const running: string[] = []
  for (const acc of targets) {
    try {
      const st = await api.fetchRefineStatus(acc.platform, acc.handle)
      if (st.state === 'running') running.push(refineKey(acc.platform, acc.handle))
    } catch {
      /* 单账号失败跳过 */
    }
  }
  refiningKeys.value = running
}

/** 精化运行态后台轮询（有在跑精化时 2s 一探，全部结束后自停） */
let refinePolling = false
function pollRefineInBackground(): void {
  if (refinePolling) return
  refinePolling = true
  void (async () => {
    try {
      while (refiningKeys.value.length > 0) {
        await new Promise((r) => setTimeout(r, 2000))
        await refreshRefineStates()
      }
    } finally {
      refinePolling = false
    }
  })()
}

/** 标记账号精化进入运行态（启动精化/打开弹窗发现运行中时调用） */
export function markRefining(platform: PlatformId, handle: string): void {
  const key = refineKey(platform, handle)
  if (!refiningKeys.value.includes(key)) {
    refiningKeys.value = [...refiningKeys.value, key]
  }
  pollRefineInBackground()
}

/** 取消运行态标记（中止/完成时调用；后台轮询也会兜底纠正） */
export function unmarkRefining(platform: PlatformId, handle: string): void {
  const key = refineKey(platform, handle)
  refiningKeys.value = refiningKeys.value.filter((k) => k !== key)
}

/* ---------- 视图状态（网址恢复由 ActivityPage 驱动） ---------- */

function init(): void {
  if (initialized.value) return
  initialized.value = true
  void (async () => {
    await ensureLoaded() // 用户组列表 + 当前组 + 信息卡
    await refreshAll()
    // 页面刷新/重开时若有账号仍在同步（服务端任务存活），接入后台轮询
    if (syncing.value) pollInBackground()
  })()
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

/** 立即同步全部账号（或当前平台视图的账号）：即时进入进行态并轮询至完成，
 * 返回本次同步范围内仍处于错误状态的账号列表（供调用方给出完成/警告提示）。
 * 引擎按账号串行去重，重复触发安全。 */
async function syncNow(): Promise<BoundAccount[]> {
  if (syncFiring.value) return []
  syncFiring.value = true
  try {
    await api.triggerSync(activePlatform.value === 'all' ? undefined : activePlatform.value)
    const statuses = await watchSyncUntilIdle()
    const scope = activePlatform.value
    return statuses.filter(
      (s) => (scope === 'all' || s.platform === scope) && s.syncState === 'error',
    )
  } finally {
    syncFiring.value = false
  }
}

/** 绑定（或换绑）账号：后端自动触发首次同步（后台执行，进度实时可见）；
 * cookie 平台携带凭据（手动输入）或留空（消费一键登录暂存凭据）。 */
async function bindAccount(
  platform: PlatformId,
  handle: string,
  opts: { displayName?: string | null; credentials?: AccountCredentials } = {},
): Promise<void> {
  await api.bindAccount(platform, handle, opts)
  await refreshAccounts() // 新账号（含同步进行态）立即可见
  pollInBackground()
}

/** 解绑并删除该账号本地数据 */
async function unbindAccount(platform: PlatformId, handle: string): Promise<void> {
  await api.unbindAccount(platform, handle)
  selectedDate.value = null
  await refreshAll()
}

/** 更新已绑定账号的凭据（仅 cookie 平台）：不删数据、不重置游标 */
async function updateAccountCredentials(
  platform: PlatformId,
  handle: string,
  credentials: AccountCredentials,
): Promise<void> {
  await api.updateCredentials(platform, handle, credentials)
  await refreshAccounts()
  pollInBackground()
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

/** 平台完整元数据（auth / browserLogin，驱动绑定弹窗凭据区渲染） */
/** 平台完整元数据（auth / browserLogin / capabilities，驱动绑定弹窗与
 * 精化按钮等能力条件渲染） */
export function platformMeta(id: PlatformId): PlatformMeta | null {
  return platforms.value.find((p) => p.id === id) ?? null
}

/** 账号展示名：优先 displayName（洛谷用户名等），空回退 handle（API 主键） */
export function accountLabel(account: BoundAccount): string {
  return account.displayName || account.handle
}

/** 「xx 前同步」标签：按视图区分衡量时间——平台视图取该平台账号的最近
 * 同步时间（各平台同步时刻可能不同，不可混用）；汇总视图取全部账号的
 * 最近一次同步时间。 */
const lastSyncLabel = computed(() => {
  const relevant =
    activePlatform.value === 'all'
      ? accounts.value
      : accounts.value.filter((a) => a.platform === activePlatform.value)
  const times = relevant
    .map((a) => a.lastSyncAt)
    .filter((t): t is string => t !== null)
    .sort()
  if (times.length === 0) return '尚未同步'
  const latest = times[times.length - 1] // ISO 升序，取最近一次同步
  const minutes = Math.max(0, Math.round((Date.now() - Date.parse(latest)) / 60000))
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

/* 切换用户组：重置视图并拉取该组数据 */
watch(currentKey, () => {
  selectedDate.value = null
  recentPage.value = 1
  dayPage.value = 1
  void refreshAll()
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
    updateAccountCredentials,
    refreshAll,
    boundOn,
    isBound,
    platformName,
    platformMeta,
    accountLabel,
  }
}
