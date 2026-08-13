/** 用户组与用户信息（样式原型阶段）：多用户组 + 组内头像 / ID / 签名，
 * localStorage 持久化。后端 data/user/<userid>/profile.json 就绪后迁移到 API，
 * 组件层不变。
 *
 * 用户组的 ID 即 profile.name（主标签）：左侧用户信息卡编辑 ID 就是
 * 重命名当前组；账号绑定与训练数据按组隔离（见 store.ts 的 groupScope）。
 */

import { computed, nextTick, reactive, watch } from 'vue'

export interface UserProfile {
  /** 主标签：ID（即用户组 ID，可重命名） */
  name: string
  /** 副标签：签名 */
  signature: string
  /** 方形头像 data URL；null 时用 ID 首字符占位 */
  avatar: string | null
}

/** 用户组：key 为数据归属的稳定内部键（重命名不影响数据），name 为可改的显示 ID */
export interface UserGroup extends UserProfile {
  key: string
}

const STORAGE_KEY = 'xcpc-helper:activity-groups'
/** 用户组功能上线前的单档案存储键，读取后整体迁入首个用户组 */
const LEGACY_KEY = 'xcpc-helper:activity-profile'
const DEFAULT_GROUP_NAME = 'default'

const storage: Storage | null = typeof localStorage === 'undefined' ? null : localStorage

interface GroupsState {
  current: string
  groups: UserGroup[]
}

function sanitizeGroup(raw: unknown): UserGroup | null {
  if (typeof raw !== 'object' || raw === null) return null
  const g = raw as Partial<UserGroup>
  if (typeof g.key !== 'string' || !g.key) return null
  return {
    key: g.key,
    name: typeof g.name === 'string' ? g.name : '',
    signature: typeof g.signature === 'string' ? g.signature : '',
    avatar: typeof g.avatar === 'string' ? g.avatar : null,
  }
}

function loadLegacy(): UserProfile {
  try {
    const raw = storage?.getItem(LEGACY_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<UserProfile>
      return {
        name: typeof parsed.name === 'string' ? parsed.name : '',
        signature: typeof parsed.signature === 'string' ? parsed.signature : '',
        avatar: typeof parsed.avatar === 'string' ? parsed.avatar : null,
      }
    }
  } catch {
    /* 本地数据损坏时回退到空档案 */
  }
  return { name: '', signature: '', avatar: null }
}

function load(): GroupsState {
  try {
    const raw = storage?.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<GroupsState>
      const groups = Array.isArray(parsed.groups)
        ? parsed.groups.map(sanitizeGroup).filter((g): g is UserGroup => g !== null)
        : []
      if (groups.length > 0) {
        const current =
          typeof parsed.current === 'string' && groups.some((g) => g.key === parsed.current)
            ? parsed.current
            : groups[0].key
        return { current, groups }
      }
    }
  } catch {
    /* 本地数据损坏时回落到初始组 */
  }
  const legacy = loadLegacy()
  return {
    current: 'default',
    groups: [{ key: 'default', ...pickProfile(legacy) }],
  }
}

function pickProfile(p: UserProfile): UserProfile {
  return { name: p.name || DEFAULT_GROUP_NAME, signature: p.signature, avatar: p.avatar }
}

const state = reactive<GroupsState>(load())

/** 初始组沿用 key 'default'，后续组用递增序号保证 key 稳定且不与组名耦合；
 * 从已有序号的最大值继续，避免与历史组的 key 冲突 */
let keyCounter = state.groups.reduce((max, g) => {
  const m = g.key.match(/^g(\d+)$/)
  return m ? Math.max(max, Number(m[1])) : max
}, state.groups.length)

watch(
  state,
  (value) => {
    try {
      storage?.setItem(STORAGE_KEY, JSON.stringify(value))
    } catch {
      /* 头像超出 localStorage 配额时静默失败，内存态本次会话仍生效 */
    }
  },
  { deep: true },
)

function currentGroup(): UserGroup {
  return state.groups.find((g) => g.key === state.current) ?? state.groups[0]
}

/** 组件层共享的当前组档案视图：与 currentGroup 双向同步 */
const profile = reactive<UserProfile>({ name: '', signature: '', avatar: null })

let syncingProfile = false

function loadProfile(): void {
  const g = currentGroup()
  syncingProfile = true
  profile.name = g.name
  profile.signature = g.signature
  profile.avatar = g.avatar
  void nextTick(() => {
    syncingProfile = false
  })
}

watch(() => state.current, loadProfile, { immediate: true })

watch(profile, (value) => {
  if (syncingProfile) return
  const g = currentGroup()
  const name = value.name.trim()
  // ID 与用户组 ID 保持同一：为空或与其他组重名时回退，不制造分歧
  if (name && name !== g.name && state.groups.some((o) => o.key !== g.key && o.name === name)) {
    loadProfile()
    return
  }
  g.name = name || g.name
  if (!name) loadProfile()
  g.signature = value.signature
  g.avatar = value.avatar
})

export function useUserGroups() {
  const groups = computed(() => state.groups)
  const currentKey = computed(() => state.current)

  /** 新建用户组并切换过去；ID 为空或重名时返回错误信息 */
  function createGroup(name: string): string | null {
    const id = name.trim()
    if (!id) return '请输入用户组 ID'
    if (state.groups.some((g) => g.name === id)) return '该用户组已存在'
    keyCounter += 1
    const group: UserGroup = { key: `g${keyCounter}`, name: id, signature: '', avatar: null }
    state.groups.push(group)
    state.current = group.key
    return null
  }

  function switchGroup(key: string): void {
    if (state.groups.some((g) => g.key === key)) state.current = key
  }

  /** 删除用户组（仅删档案，第一期训练数据不按组隔离）；
   * 仅剩一个组或 key 不存在时返回错误信息；删除当前组则切换到剩余首个组 */
  function deleteGroup(key: string): string | null {
    if (state.groups.length <= 1) return '至少保留一个用户组'
    const index = state.groups.findIndex((g) => g.key === key)
    if (index < 0) return '用户组不存在'
    state.groups.splice(index, 1)
    if (state.current === key) state.current = state.groups[0].key
    return null
  }

  return { groups, currentKey, createGroup, switchGroup, deleteGroup }
}

/** 读取图片文件，居中裁剪并缩放为方形头像 data URL（控制 localStorage 体积） */
export async function fileToAvatar(file: File, size = 128): Promise<string> {
  const bitmap = await createImageBitmap(file)
  try {
    const side = Math.min(bitmap.width, bitmap.height)
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('canvas 2d 上下文不可用')
    ctx.drawImage(
      bitmap,
      (bitmap.width - side) / 2,
      (bitmap.height - side) / 2,
      side,
      side,
      0,
      0,
      size,
      size,
    )
    return canvas.toDataURL('image/jpeg', 0.85)
  } finally {
    bitmap.close()
  }
}

export function useProfile() {
  return { profile }
}
