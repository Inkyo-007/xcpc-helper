/** 用户组与用户信息（后端驱动）。
 *
 * 用户组 = data/user/<user_id>/ 目录（目录名即组名，支持中文），
 * 新建/重命名同步目录名，删除物理删除；切换组后其余 API 作用于新组。
 * 信息卡（ID / 签名 / 头像）存于组内 profile.json，与组名分离、
 * 独立编辑（ID 编辑不影响组名，组名编辑不影响 ID）。
 * 组件层接口与旧 localStorage 版本保持一致。
 */

import { computed, reactive, ref, watch } from 'vue'
import * as api from '@/features/activity/api'

export interface UserProfile {
  /** 主标签：信息卡显示 ID（独立于用户组名） */
  name: string
  /** 副标签：签名 */
  signature: string
  /** 方形头像 data URL；null 时用 ID 首字符占位 */
  avatar: string | null
}

/** 用户组：key 与 name 均为目录名（组名），由后端返回 */
export interface UserGroup {
  key: string
  name: string
}

const groups = ref<UserGroup[]>([])
const currentKey = ref('')

/** 组件层共享的当前组档案视图：编辑时防抖提交后端 */
const profile = reactive<UserProfile>({ name: '', signature: '', avatar: null })

/** loadProfile 同步中标记，避免 watch 回写 */
let syncingProfile = false
let saveTimer: ReturnType<typeof setTimeout> | null = null

function applyProfile(p: api.ApiProfile): void {
  syncingProfile = true
  profile.name = p.id
  profile.signature = p.signature
  profile.avatar = p.avatar
  syncingProfile = false
}

async function loadProfile(): Promise<void> {
  try {
    applyProfile(await api.fetchProfile())
  } catch {
    /* 后端暂不可用时保持现有档案 */
  }
}

async function refreshGroups(): Promise<void> {
  const res = await api.fetchGroups()
  groups.value = res.groups.map((g) => ({ key: g.name, name: g.name }))
  const current = res.groups.find((g) => g.current)
  if (current) {
    currentKey.value = current.name
    await loadProfile()
  }
}

/** 首次加载（页面 init 时调用） */
let loaded = false
async function ensureLoaded(): Promise<void> {
  if (loaded) return
  loaded = true
  await refreshGroups()
}

/** 错误信息提取（供组件提示） */
function errMsg(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback
}

async function createGroup(name: string): Promise<string | null> {
  try {
    await api.createGroup(name)
    await refreshGroups()
    return null
  } catch (e) {
    return errMsg(e, '创建用户组失败')
  }
}

async function switchGroup(key: string): Promise<string | null> {
  try {
    await api.switchGroup(key)
    await refreshGroups()
    return null
  } catch (e) {
    return errMsg(e, '切换用户组失败')
  }
}

/** 重命名当前用户组（目录名同步，数据归属不变） */
async function renameGroup(newName: string): Promise<string | null> {
  try {
    await api.renameGroup(currentKey.value, newName)
    await refreshGroups()
    return null
  } catch (e) {
    return errMsg(e, '重命名失败')
  }
}

/** 删除当前用户组（含账号绑定、训练数据与信息卡，不可找回） */
async function deleteGroup(): Promise<string | null> {
  try {
    await api.deleteGroup(currentKey.value)
    await refreshGroups()
    return null
  } catch (e) {
    return errMsg(e, '删除用户组失败')
  }
}

/* 信息卡编辑：防抖提交后端（ID 与组名分离，不影响组名） */
watch(
  profile,
  (value) => {
    if (syncingProfile) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(async () => {
      try {
        await api.updateProfile({
          id: value.name,
          signature: value.signature,
          avatar: value.avatar,
        })
      } catch (e) {
        /* 保存失败保持内存态，下次编辑重试 */
        console.error('信息卡保存失败', e)
      }
    }, 400)
  },
  { deep: true },
)

export function useUserGroups() {
  const list = computed(() => groups.value)
  const current = computed(() => currentKey.value)

  return {
    groups: list,
    currentKey: current,
    ensureLoaded,
    createGroup,
    switchGroup,
    renameGroup,
    deleteGroup,
  }
}

/** 读取图片文件，居中裁剪并缩放为方形头像 data URL。
 * 512px 保证信息卡显示（约 268px 容器）有 2 倍超采样，避免模糊。 */
export async function fileToAvatar(file: File, size = 512): Promise<string> {
  const bitmap = await createImageBitmap(file)
  try {
    const side = Math.min(bitmap.width, bitmap.height)
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('canvas 2d 上下文不可用')
    ctx.imageSmoothingQuality = 'high'
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
    return canvas.toDataURL('image/jpeg', 0.9)
  } finally {
    bitmap.close()
  }
}

export function useProfile() {
  return { profile }
}
