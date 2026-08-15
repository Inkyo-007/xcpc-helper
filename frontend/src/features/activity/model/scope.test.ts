import { describe, expect, it } from 'vitest'
import {
  findPlatformAccount,
  hasAccountForScope,
  needsUserInfoRefresh,
  resolveProfileAvatar,
} from '@/features/activity/model/scope'
import type { BoundAccount } from '@/features/activity/types'

const codeforces: BoundAccount = {
  platform: 'codeforces',
  handle: 'tourist',
  displayName: 'tourist',
  avatar: 'https://example.com/avatar.png',
  userInfoReady: true,
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

describe('needsUserInfoRefresh', () => {
  it('只有全部账号明确完成回填时才跳过', () => {
    expect(needsUserInfoRefresh([])).toBe(false)
    expect(needsUserInfoRefresh([{ userInfoReady: true }])).toBe(false)
    expect(needsUserInfoRefresh([{ userInfoReady: false }])).toBe(true)
    expect(needsUserInfoRefresh([{}])).toBe(true)
  })
})

describe('resolveProfileAvatar', () => {
  it('自定义头像优先，未设置时才回退平台头像', () => {
    expect(resolveProfileAvatar('data:image/jpeg;base64,custom', 'https://avatar')).toBe(
      'data:image/jpeg;base64,custom',
    )
    expect(resolveProfileAvatar(null, 'https://avatar')).toBe('https://avatar')
    expect(resolveProfileAvatar(null, null)).toBeNull()
  })
})
