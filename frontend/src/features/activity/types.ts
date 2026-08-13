/** 训练统计（activity）域类型。与后端 schemas 对齐；mock 阶段仅覆盖第一期范围。 */

export type PlatformId = 'codeforces' | 'atcoder' | 'luogu' | 'leetcode-cn' | 'nowcoder'

export interface PlatformMeta {
  id: PlatformId
  name: string
}

/** 已绑定账号及其同步状态 */
export interface BoundAccount {
  platform: PlatformId
  handle: string
  /** ISO 时间；null 表示从未同步成功 */
  lastSyncAt: string | null
  syncState: 'idle' | 'running' | 'error'
  /** syncState 为 error 时的诊断信息 */
  syncError?: string
}

/** 单日聚合（后端按本地时区切天后返回） */
export interface DayActivity {
  /** YYYY-MM-DD（本地时区） */
  date: string
  submissions: number
  /** 当天 AC 的不同题目数 */
  solved: number
}

export interface OverviewTotals {
  totalSolved: number
  totalSubmissions: number
  todaySolved: number
  weekSolved: number
  streakDays: number
}

export interface OverviewData {
  totals: OverviewTotals
  /** 近约 370 天的日序列，按日期升序，末尾为今天 */
  daily: DayActivity[]
}

/** 评测结果；JG = 评测中（如 Codeforces 的 SUBMITTED / TESTING） */
export type Verdict = 'AC' | 'WA' | 'CE' | 'RE' | 'TLE' | 'MLE' | 'OLE' | 'UKE' | 'JG'

export interface SubmissionEntry {
  id: string
  platform: PlatformId
  problemKey: string
  problemName: string
  problemUrl: string
  verdict: Verdict
  language: string
  /** HH:mm（本地时区） */
  time: string
}

/** 近期提交列表条目：带所属日期，跨天合并后按时间倒序展示 */
export interface RecentSubmission extends SubmissionEntry {
  /** YYYY-MM-DD（本地时区） */
  date: string
}
