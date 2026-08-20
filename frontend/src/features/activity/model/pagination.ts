/** 近期提交分页（纯函数）：每页固定 10 条，页码从 1 起。 */

export const RECENT_PAGE_SIZE = 10

export function pageCount(total: number, size: number = RECENT_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / size))
}

/** 取某页的切片；页码越界时夹紧到有效范围 */
export function paged<T>(list: T[], page: number, size: number = RECENT_PAGE_SIZE): T[] {
  const current = Math.min(Math.max(1, page), pageCount(list.length, size))
  return list.slice((current - 1) * size, current * size)
}
