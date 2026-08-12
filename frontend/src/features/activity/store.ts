/** 训练统计数据 store（单例）。
 *
 * 样式原型阶段：数据全部来自 model/mock.ts 的确定性伪随机生成，
 * 接口形状与后端 API 对齐；后端就绪后仅需把 init/bind/sync 等
 * 动作替换为真实请求，组件层无需改动。
 */

import { computed, reactive, ref } from 'vue'
import { generateDaily, generateEntries, historyOffset } from '@/features/activity/model/mock'
import type {
  BoundAccount,
  DayActivity,
  OverviewTotals,
  PlatformId,
  RecentSubmission,
  SubmissionEntry,
} from '@/features/activity/types'

export type PlatformScope = 'all' | PlatformId

const accounts = ref<BoundAccount[]>([])
const activePlatform = ref<PlatformScope>('all')
const selectedDate = ref<string | null>(null)
/** 近期提交列表的分页页码（从 1 起；当日明细模式不分页） */
const recentPage = ref(1)
const syncing = ref(false)
const initialized = ref(false)

/** 每账号的日序列（key 为 `platform/handle`） */
const dailyByAccount = reactive<Record<string, DayActivity[]>>({})

function accountKey(platform: PlatformId, handle: string): string {
  return `${platform}/${handle}`
}

function scopedAccounts(): BoundAccount[] {
  if (activePlatform.value === 'all') return accounts.value
  return accounts.value.filter((a) => a.platform === activePlatform.value)
}

/** 当前视图（汇总或单平台）合并后的日序列 */
const mergedDaily = computed<DayActivity[]>(() => {
  const merged = new Map<string, DayActivity>()
  for (const acc of scopedAccounts()) {
    for (const day of dailyByAccount[accountKey(acc.platform, acc.handle)] ?? []) {
      const cur = merged.get(day.date)
      if (cur) {
        cur.submissions += day.submissions
        cur.solved += day.solved
      } else {
        merged.set(day.date, { ...day })
      }
    }
  }
  return [...merged.values()].sort((a, b) => a.date.localeCompare(b.date))
})

/** all-time 总量 = 日序列之和 + 每账号历史偏移（mock 口径） */
const totals = computed<OverviewTotals>(() => {
  const daily = mergedDaily.value
  let totalSolved = 0
  let totalSubmissions = 0
  for (const acc of scopedAccounts()) {
    const off = historyOffset(accountKey(acc.platform, acc.handle))
    totalSolved += off.solved
    totalSubmissions += off.submissions
  }
  for (const d of daily) {
    totalSolved += d.solved
    totalSubmissions += d.submissions
  }
  const last7 = daily.slice(-7)
  let streakDays = 0
  let i = daily.length - 1
  // 今天尚无 AC 时不算断签，从昨天起向前数
  if (i >= 0 && daily[i].solved === 0) i--
  for (; i >= 0 && daily[i].solved > 0; i--) streakDays++
  return {
    totalSolved,
    totalSubmissions,
    todaySolved: daily.at(-1)?.solved ?? 0,
    weekSolved: last7.reduce((s, d) => s + d.solved, 0),
    streakDays,
  }
})

const entries = computed<SubmissionEntry[]>(() => {
  const date = selectedDate.value
  if (!date) return []
  const out: SubmissionEntry[] = []
  for (const acc of scopedAccounts()) {
    const day = (dailyByAccount[accountKey(acc.platform, acc.handle)] ?? []).find(
      (d) => d.date === date,
    )
    if (day && day.submissions > 0) out.push(...generateEntries(acc.platform, acc.handle, day))
  }
  return out.sort((a, b) => b.time.localeCompare(a.time))
})

/** 近期提交的扫描窗口与条数上限（mock 阶段足够覆盖一个滚动列表） */
const RECENT_DAYS = 21
const RECENT_LIMIT = 60

/** 近期提交：近 RECENT_DAYS 天内有提交的日子，跨账号合并，按时间倒序 */
const recentEntries = computed<RecentSubmission[]>(() => {
  const out: RecentSubmission[] = []
  for (const acc of scopedAccounts()) {
    const days = dailyByAccount[accountKey(acc.platform, acc.handle)] ?? []
    for (let i = days.length - 1; i >= 0 && i >= days.length - RECENT_DAYS; i--) {
      const day = days[i]
      if (day.submissions === 0) continue
      for (const e of generateEntries(acc.platform, acc.handle, day)) {
        out.push({ ...e, date: day.date })
      }
    }
  }
  return out
    .sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`))
    .slice(0, RECENT_LIMIT)
})

const lastSyncLabel = computed(() => {
  const times = scopedAccounts()
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

function seedDaily(acc: BoundAccount): void {
  dailyByAccount[accountKey(acc.platform, acc.handle)] = generateDaily(
    accountKey(acc.platform, acc.handle),
  )
}

function init(): void {
  if (initialized.value) return
  initialized.value = true
  const demo: BoundAccount[] = [
    {
      platform: 'codeforces',
      handle: 'demo_coder',
      lastSyncAt: new Date(Date.now() - 12 * 60000).toISOString(),
      syncState: 'idle',
    },
    {
      platform: 'atcoder',
      handle: 'kyopro_demo',
      lastSyncAt: new Date(Date.now() - 47 * 60000).toISOString(),
      syncState: 'idle',
    },
  ]
  accounts.value = demo
  demo.forEach(seedDaily)
}

function setPlatform(scope: PlatformScope): void {
  activePlatform.value = scope
  selectedDate.value = null
  recentPage.value = 1
}

/** 选中某天查看当日明细；再次点击同一格子取消选中，回到近期提交 */
function selectDate(date: string): void {
  selectedDate.value = selectedDate.value === date ? null : date
}

function setRecentPage(page: number): void {
  recentPage.value = page
}

/** mock 同步：模拟耗时后刷新同步时间 */
async function syncNow(): Promise<void> {
  if (syncing.value) return
  syncing.value = true
  for (const acc of accounts.value) acc.syncState = 'running'
  await new Promise((r) => setTimeout(r, 1400))
  const now = new Date().toISOString()
  for (const acc of accounts.value) {
    acc.syncState = 'idle'
    acc.lastSyncAt = now
  }
  syncing.value = false
}

/** mock 绑定：生成该账号数据并立即"同步" */
async function bindAccount(platform: PlatformId, handle: string): Promise<void> {
  const acc: BoundAccount = { platform, handle, lastSyncAt: null, syncState: 'running' }
  accounts.value.push(acc)
  seedDaily(acc)
  await new Promise((r) => setTimeout(r, 900))
  acc.syncState = 'idle'
  acc.lastSyncAt = new Date().toISOString()
}

function unbindAccount(platform: PlatformId, handle: string): void {
  accounts.value = accounts.value.filter(
    (a) => !(a.platform === platform && a.handle === handle),
  )
  delete dailyByAccount[accountKey(platform, handle)]
  if (activePlatform.value !== 'all' && !scopedAccounts().length) activePlatform.value = 'all'
  selectedDate.value = null
}

/** 判断 handle 是否已被绑定（mock 验证用） */
function isBound(platform: PlatformId, handle: string): boolean {
  return accounts.value.some((a) => a.platform === platform && a.handle === handle)
}

export function useActivity() {
  return {
    accounts,
    activePlatform,
    selectedDate,
    recentPage,
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
    setRecentPage,
    syncNow,
    bindAccount,
    unbindAccount,
    isBound,
  }
}
