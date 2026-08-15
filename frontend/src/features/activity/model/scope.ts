/** 训练统计账号作用域与信息卡数据选择的纯函数。 */

import type { BoundAccount, PlatformId } from '@/features/activity/types'

export type AccountScope = 'all' | PlatformId

export function findPlatformAccount(
  accounts: readonly BoundAccount[],
  platform: PlatformId,
): BoundAccount | null {
  return accounts.find((account) => account.platform === platform) ?? null
}

export function hasAccountForScope(
  accounts: readonly BoundAccount[],
  scope: AccountScope,
): boolean {
  return scope === 'all' ? accounts.length > 0 : findPlatformAccount(accounts, scope) !== null
}

/** 旧数据没有该字段；只有明确为 true 才视为已完成资料回填。 */
export function needsUserInfoRefresh(
  accounts: readonly { userInfoReady?: boolean }[],
): boolean {
  return accounts.some((account) => account.userInfoReady !== true)
}

/** 用户自定义头像优先；未设置时单平台视图回退平台头像。 */
export function resolveProfileAvatar(
  profileAvatar: string | null | undefined,
  platformAvatar: string | null | undefined,
): string | null {
  return profileAvatar || platformAvatar || null
}
