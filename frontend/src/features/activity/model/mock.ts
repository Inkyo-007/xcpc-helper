/** 样式原型阶段的确定性 mock 数据（后端接入后整体删除，勿在组件外引用）。
 * 用固定种子伪随机生成，保证每次打开页面看到同一份"训练记录"。
 */

import type { DayActivity, PlatformId, PlatformMeta, SubmissionEntry, Verdict } from '@/features/activity/types'
import { addDays, parseDate, todayStr } from '@/features/activity/model/dates'

export const PLATFORMS: PlatformMeta[] = [
  { id: 'codeforces', name: 'Codeforces' },
  { id: 'atcoder', name: 'AtCoder' },
  { id: 'luogu', name: '洛谷' },
  { id: 'leetcode-cn', name: 'LeetCode' },
  { id: 'nowcoder', name: '牛客竞赛' },
]

export function platformName(id: PlatformId): string {
  return PLATFORMS.find((p) => p.id === id)?.name ?? id
}

/** mulberry32：小而稳定的种子随机数 */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function hashSeed(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

/** 生成近 days 天的日序列：周末更活跃，偶发冲刺与空窗 */
export function generateDaily(seedKey: string, days = 370): DayActivity[] {
  const rand = mulberry32(hashSeed(seedKey))
  const end = todayStr()
  const out: DayActivity[] = []
  for (let i = days - 1; i >= 0; i--) {
    const date = addDays(end, -i)
    const dow = parseDate(date).getDay()
    const weekendBoost = dow === 0 || dow === 6 ? 0.18 : 0
    const active = rand() < 0.52 + weekendBoost
    if (!active) {
      out.push({ date, submissions: 0, solved: 0 })
      continue
    }
    const burst = rand() < 0.12 ? 6 : 0
    const submissions = 1 + Math.floor(rand() * rand() * 8) + Math.floor(rand() * (burst + 1))
    const acRatio = 0.25 + rand() * 0.65
    const solved = Math.min(submissions, Math.round(submissions * acRatio))
    out.push({ date, submissions, solved })
  }
  return out
}

/** 账号的历史总量偏移（日序列只覆盖近一年，all-time 总量需要前置基数） */
export function historyOffset(seedKey: string): { solved: number; submissions: number } {
  const rand = mulberry32(hashSeed(`offset:${seedKey}`))
  const solved = 180 + Math.floor(rand() * 420)
  return { solved, submissions: solved * (2 + Math.floor(rand() * 3)) }
}

interface ProblemSeed {
  key: string
  name: string
}

const PROBLEM_POOLS: Record<PlatformId, ProblemSeed[]> = {
  codeforces: [
    { key: '1986A', name: 'X Axis' },
    { key: '1985B', name: 'Maximum Multiple Sum' },
    { key: '1992C', name: 'Squaring' },
    { key: '1974D', name: 'Ingenuity-2' },
    { key: '2008B', name: 'Square or Not' },
    { key: '1988C', name: 'Make Permutation' },
  ],
  atcoder: [
    { key: 'abc350_a', name: 'Past ABCs' },
    { key: 'abc349_b', name: 'Commencement' },
    { key: 'abc352_c', name: 'Standing On The Shoulders' },
    { key: 'abc347_d', name: 'Popcount and XOR' },
    { key: 'abc355_b', name: 'Intersection of Cuboids' },
    { key: 'abc346_c', name: 'Σ' },
  ],
  luogu: [
    { key: 'P1001', name: 'A+B Problem' },
    { key: 'P3370', name: '字符串哈希' },
    { key: 'P1908', name: '逆序对' },
    { key: 'P3367', name: '并查集模板' },
    { key: 'P4779', name: '单源最短路径' },
    { key: 'P3919', name: '可持久化数组' },
  ],
  'leetcode-cn': [
    { key: 'two-sum', name: '两数之和' },
    { key: 'lrucache', name: 'LRU 缓存' },
    { key: 'median-sorted', name: '寻找两个正序数组的中位数' },
    { key: 'regex-match', name: '正则表达式匹配' },
  ],
  nowcoder: [
    { key: 'NC14532', name: '合唱团' },
    { key: 'NC20345', name: '星际穿越' },
    { key: 'NC51173', name: '整数的各位积和之差' },
  ],
}

function problemUrl(platform: PlatformId, key: string): string {
  if (platform === 'codeforces') {
    const m = key.match(/^(\d+)([A-Z])$/)
    return m ? `https://codeforces.com/problemset/problem/${m[1]}/${m[2]}` : 'https://codeforces.com'
  }
  if (platform === 'atcoder') {
    const contest = key.split('_')[0]
    return `https://atcoder.jp/contests/${contest}/tasks/${key}`
  }
  if (platform === 'luogu') return `https://www.luogu.com.cn/problem/${key}`
  if (platform === 'leetcode-cn') return `https://leetcode.cn/problems/${key}/`
  return `https://ac.nowcoder.com/`
}

const LANGUAGES = ['C++17', 'C++20', 'C++20', 'Python3', 'C++17', 'Java21']
const FAIL_VERDICTS: Verdict[] = ['WA', 'WA', 'WA', 'CE', 'RE', 'TLE', 'MLE', 'OLE', 'UKE', 'JG']

/** 生成某 (账号, 日期) 的提交明细，数量与当日聚合一致 */
export function generateEntries(
  platform: PlatformId,
  handle: string,
  day: DayActivity,
): SubmissionEntry[] {
  const rand = mulberry32(hashSeed(`entries:${platform}:${handle}:${day.date}`))
  const pool = PROBLEM_POOLS[platform]
  const failed = day.submissions - day.solved
  const used = new Set<number>()
  const pick = (): ProblemSeed => {
    // 爆发日的提交数可超过题库量：题库抽完后允许重复取题，
    // 否则 while 永远找不到未用过的下标，死循环把整页卡死
    if (used.size >= pool.length) {
      return pool[Math.floor(rand() * pool.length)]
    }
    let idx = Math.floor(rand() * pool.length)
    while (used.has(idx)) idx = (idx + 1) % pool.length
    used.add(idx)
    return pool[idx]
  }
  const out: SubmissionEntry[] = []
  for (let i = 0; i < day.submissions; i++) {
    const p = pick()
    const isAc = i >= failed
    const verdict: Verdict = isAc ? 'AC' : FAIL_VERDICTS[Math.floor(rand() * FAIL_VERDICTS.length)]
    const hour = 8 + Math.floor(rand() * 15)
    const minute = Math.floor(rand() * 60)
    out.push({
      id: `${platform}-${handle}-${day.date}-${i}`,
      platform,
      problemKey: p.key,
      problemName: p.name,
      problemUrl: problemUrl(platform, p.key),
      verdict,
      language: LANGUAGES[Math.floor(rand() * LANGUAGES.length)],
      time: `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`,
    })
  }
  return out.sort((a, b) => a.time.localeCompare(b.time))
}
