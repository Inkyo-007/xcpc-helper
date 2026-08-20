/** 本地时区日期工具（纯函数）。日序列的"天"一律按用户本地时区。 */

export function toDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function parseDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(s: string, n: number): string {
  const d = parseDate(s)
  d.setDate(d.getDate() + n)
  return toDateStr(d)
}

export function todayStr(): string {
  return toDateStr(new Date())
}

/** YYYY-MM-DD → YYYY-MM */
export function monthKey(s: string): string {
  return s.slice(0, 7)
}

/** 近期提交的行底日期：当年省略年份（MM-DD），往年显示完整 YYYY-MM-DD */
export function recentDateStr(date: string, today: string = todayStr()): string {
  return date.slice(0, 4) === today.slice(0, 4) ? date.slice(5) : date
}

const WEEKDAY_CN = ['日', '一', '二', '三', '四', '五', '六']

export function weekdayCn(s: string): string {
  return WEEKDAY_CN[parseDate(s).getDay()]
}
