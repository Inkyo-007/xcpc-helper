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

/* ---------- 技能树 ---------- */

/** 技能节点（一个 CF 标签） */
export interface SkillNode {
  key: string
  name: string
  tag: string
  /** 掌握度 0~1 */
  proficiency: number
  acCount: number
  maxDifficulty: number | null
}

/** 技能域节点 */
export interface SkillDomain {
  key: string
  name: string
  proficiency: number
  acCount: number
  maxDifficulty: number | null
  skills: SkillNode[]
}

export interface SkillTreeTotals {
  acCount: number
  proficiency: number
  maxDifficulty: number | null
}

export interface SkillTreeData {
  domains: SkillDomain[]
  totals: SkillTreeTotals
}

/* ---------- 训练分析 ---------- */

/** 难度分档（按 rating 分桶，非数值难度归「未知」） */
export interface DifficultyBand {
  label: string
  min: number | null
  max: number | null
  /** 去重 AC 题数 */
  solvedCount: number
  /** 去重尝试题数（任意 verdict） */
  attemptCount: number
  /** 该档提交总数 */
  submissionCount: number
  /** solvedCount / attemptCount（无尝试为 0） */
  passRate: number
}

export interface VerdictCount {
  verdict: Verdict
  count: number
  /** count / total（total 为 0 时 share=0） */
  share: number
}

/** 单周活跃（weekStart 为 ISO 日期，周一） */
export interface WeekActivity {
  weekStart: string
  /** 去重 AC 题数 */
  solved: number
  /** 提交总数 */
  attempts: number
  /** 有提交的不同天数 */
  activeDays: number
}

export interface HourActivity {
  /** 0~23 */
  hour: number
  count: number
}

export interface Rhythm {
  /** 近 12 周（含本周），升序，末尾为本周期 */
  weeks: WeekActivity[]
  /** 0~23 小时提交数 */
  hours: HourActivity[]
}

/** 薄弱点（与技能树同口径：仅 CF 标签参与） */
export interface WeakPoint {
  key: string
  name: string
  domainKey: string
  domainName: string
  solvedCount: number
  attemptCount: number
  passRate: number
  /** 0~1，复用 skill_tree.proficiency 口径 */
  proficiency: number
  maxDifficulty: number | null
  suggestion: string
}

/** 四维聚合（对应后端 AnalysisOut） */
export interface AnalysisData {
  difficulty: DifficultyBand[]
  verdicts: VerdictCount[]
  rhythm: Rhythm
  weakPoints: WeakPoint[]
}

/* ---------- AI 分析报告 ---------- */

/** AI 分析报告正文（对应后端 ReportOut） */
export interface AnalysisReportData {
  /** markdown 正文 */
  content: string
  /** llm = 在线模型生成；rule = 未配置/失败时规则化降级报告 */
  source: 'llm' | 'rule'
  /** source === 'llm' 时使用的模型名；否则 null */
  model: string | null
  /** 规则化降级时的说明文案；否则 null */
  note: string | null
}

/** 报告生成配置（对应后端 ReportConfigOut；不泄露 api_key） */
export interface ReportConfig {
  /** api_key 是否已配置（false 时生成规则化报告） */
  configured: boolean
  model: string
  baseUrl: string
}
