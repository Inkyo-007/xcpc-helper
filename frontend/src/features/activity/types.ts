/** 训练统计（activity）域类型。与后端 schemas 对齐；mock 阶段仅覆盖第一期范围。 */

export type PlatformId = 'codeforces' | 'atcoder' | 'luogu' | 'leetcode-cn' | 'nowcoder'

/** 平台凭据（cookie 授权平台；与后端 adapters.base.Credentials 对齐） */
export interface AccountCredentials {
  cookies?: Record<string, string>
  headers?: Record<string, string>
}

export interface PlatformMeta {
  id: PlatformId
  name: string
  /** 凭据需求：none 匿名可取 / cookie 需登录授权（洛谷等） */
  auth: 'none' | 'cookie'
  /** 一键登录可用（cookie 平台且服务端具备浏览器登录能力） */
  browserLogin: boolean
}

/** 已绑定账号及其同步状态 */
export interface BoundAccount {
  platform: PlatformId
  handle: string
  /** 展示名（洛谷用户名等）；空则界面回退显示 handle */
  displayName?: string | null
  /** 当前平台账号头像；上传自定义头像后替换为本地 data URL */
  avatar?: string | null
  /** ISO 时间；null 表示从未同步成功 */
  lastSyncAt: string | null
  syncState: 'idle' | 'running' | 'error'
  /** syncState 为 error 时的诊断信息 */
  syncError?: string
  /** 结构化错误码；auth_expired = 凭据过期，引导重新授权 */
  syncErrorCode?: string | null
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
