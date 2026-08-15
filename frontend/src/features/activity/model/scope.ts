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

/** 汇总视图使用用户组头像；单平台视图使用当前账号头像。 */
export function resolveProfileAvatar(
  profileAvatar: string | null | undefined,
  account: Pick<BoundAccount, 'avatar'> | null,
): string | null {
  if (account) return account.avatar || null
  return profileAvatar || null
}
