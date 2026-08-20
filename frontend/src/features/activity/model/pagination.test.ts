import { describe, expect, it } from 'vitest'
import { pageCount, paged, RECENT_PAGE_SIZE } from '@/features/activity/model/pagination'

describe('pageCount', () => {
  it('空列表也有 1 页', () => {
    expect(pageCount(0)).toBe(1)
  })

  it('按每页 10 条向上取整', () => {
    expect(pageCount(RECENT_PAGE_SIZE)).toBe(1)
    expect(pageCount(11)).toBe(2)
    expect(pageCount(60)).toBe(6)
  })
})

describe('paged', () => {
  const list = Array.from({ length: 25 }, (_, i) => i)

  it('取对应页的 10 条切片', () => {
    expect(paged(list, 1)).toEqual(list.slice(0, 10))
    expect(paged(list, 2)).toEqual(list.slice(10, 20))
    expect(paged(list, 3)).toEqual(list.slice(20, 25))
  })

  it('页码越界时夹紧到有效范围', () => {
    expect(paged(list, 0)).toEqual(list.slice(0, 10))
    expect(paged(list, 99)).toEqual(list.slice(20, 25))
  })
})
