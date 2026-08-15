import { describe, expect, it } from 'vitest'
import {
  findPlatformAccount,
  hasAccountForScope,
  resolveProfileAvatar,
} from '@/features/activity/model/scope'
import type { BoundAccount } from '@/features/activity/types'

const codeforces: BoundAccount = {
  platform: 'codeforces',
  handle: 'tourist',
  displayName: 'tourist',
  avatar: 'https://example.com/avatar.png',
  lastSyncAt: null,
  syncState: 'idle',
}

describe('findPlatformAccount', () => {
  it('只返回指定平台的绑定账号', () => {
    expect(findPlatformAccount([codeforces], 'codeforces')).toBe(codeforces)
    expect(findPlatformAccount([codeforces], 'atcoder')).toBeNull()
  })
})

describe('hasAccountForScope', () => {
  it('汇总视图只要存在任一绑定账号即可展示', () => {
    expect(hasAccountForScope([codeforces], 'all')).toBe(true)
    expect(hasAccountForScope([], 'all')).toBe(false)
  })

  it('单平台视图必须绑定当前平台', () => {
    expect(hasAccountForScope([codeforces], 'codeforces')).toBe(true)
    expect(hasAccountForScope([codeforces], 'atcoder')).toBe(false)
  })
})

describe('resolveProfileAvatar', () => {
  it('汇总头像与各平台账号头像互相隔离', () => {
    const groupAvatar = 'data:image/jpeg;base64,group'
    const platformAccount = {
      avatar: 'data:image/jpeg;base64,codeforces',
    }
    expect(resolveProfileAvatar(groupAvatar, null)).toBe(groupAvatar)
    expect(resolveProfileAvatar(groupAvatar, platformAccount)).toBe(
      'data:image/jpeg;base64,codeforces',
    )
    expect(resolveProfileAvatar(groupAvatar, { avatar: 'https://atcoder' })).toBe(
      'https://atcoder',
    )
    expect(resolveProfileAvatar(null, { avatar: null })).toBeNull()
  })
})
