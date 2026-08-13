/** activity 后端 API 客户端（与后端 modules/activity/schemas.py 对齐）。 */

import { request } from '@/shared/api/client'
import type {
  BoundAccount,
  DayActivity,
  OverviewTotals,
  PlatformId,
  PlatformMeta,
  SubmissionEntry,
} from '@/features/activity/types'
import type { PlatformScope } from '@/features/activity/store'

export interface ApiPlatformMeta extends PlatformMeta {
  capabilities: string[]
  auth: string
  /** 该平台当前绑定账号；未绑定为 null */
  account: BoundAccount | null
}

export interface ApiPlatformsResponse {
  platforms: ApiPlatformMeta[]
}

export interface ApiVerifyResponse {
  platform: string
  handle: string
  avatar: string | null
}

export interface ApiOverviewResponse {
  totals: OverviewTotals
  /** 近约 370 天日序列，升序，末尾为今天 */
  daily: DayActivity[]
}

/** 提交条目：date 为本地时区日期（近期提交与当日明细共用） */
export interface ApiSubmission extends SubmissionEntry {
  date: string
}

export interface ApiSubmissionsResponse {
  items: ApiSubmission[]
}

function scopeParam(scope: PlatformScope): string {
  return scope === 'all' ? '' : scope
}

export function fetchPlatforms(): Promise<ApiPlatformsResponse> {
  return request<ApiPlatformsResponse>('/activity/platforms')
}

export function verifyAccount(platform: string, handle: string): Promise<ApiVerifyResponse> {
  return request<ApiVerifyResponse>('/activity/accounts/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform, handle }),
  })
}

export function bindAccount(platform: string, handle: string): Promise<BoundAccount> {
  return request<BoundAccount>('/activity/accounts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform, handle }),
  })
}

export function unbindAccount(platform: string, handle: string): Promise<void> {
  const path = `/activity/accounts/${encodeURIComponent(platform)}/${encodeURIComponent(handle)}`
  return request<void>(path, { method: 'DELETE' })
}

export function fetchOverview(scope: PlatformScope = 'all'): Promise<ApiOverviewResponse> {
  const platform = scopeParam(scope)
  return request<ApiOverviewResponse>(`/activity/overview${platform ? `?platform=${platform}` : ''}`)
}

export function fetchSubmissions(opts: {
  date?: string | null
  platform?: PlatformScope
} = {}): Promise<ApiSubmissionsResponse> {
  const params = new URLSearchParams()
  if (opts.date) params.set('date', opts.date)
  const platform = opts.platform ? scopeParam(opts.platform) : ''
  if (platform) params.set('platform', platform)
  const qs = params.toString()
  return request<ApiSubmissionsResponse>(`/activity/submissions${qs ? `?${qs}` : ''}`)
}

export function triggerSync(platform?: PlatformId): Promise<void> {
  return request<void>('/activity/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(platform ? { platform } : {}),
  })
}

export function fetchSyncStatus(): Promise<BoundAccount[]> {
  return request<BoundAccount[]>('/activity/sync/status')
}

/* ---------- 用户组与信息卡 ---------- */

export interface ApiGroup {
  name: string
  current: boolean
}

export interface ApiGroupsResponse {
  groups: ApiGroup[]
}

export interface ApiProfile {
  id: string
  signature: string
  avatar: string | null
}

export function fetchGroups(): Promise<ApiGroupsResponse> {
  return request<ApiGroupsResponse>('/activity/groups')
}

export function createGroup(name: string): Promise<ApiGroup> {
  return request<ApiGroup>('/activity/groups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function renameGroup(name: string, newName: string): Promise<ApiGroupsResponse> {
  return request<ApiGroupsResponse>(
    `/activity/groups/${encodeURIComponent(name)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ newName }),
    },
  )
}

export function deleteGroup(name: string): Promise<void> {
  return request<void>(`/activity/groups/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
}

export function switchGroup(name: string): Promise<ApiGroup> {
  return request<ApiGroup>('/activity/current-group', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function fetchProfile(): Promise<ApiProfile> {
  return request<ApiProfile>('/activity/profile')
}

export function updateProfile(payload: {
  id?: string
  signature?: string
  avatar?: string | null
}): Promise<ApiProfile> {
  return request<ApiProfile>('/activity/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
