/** 用户信息（样式原型阶段）：头像 / ID / 签名，localStorage 持久化。
 * 后端 data/user/<userid>/profile.json 就绪后迁移到 API，组件层不变。
 */

import { reactive, watch } from 'vue'

export interface UserProfile {
  /** 主标签：ID */
  name: string
  /** 副标签：签名 */
  signature: string
  /** 方形头像 data URL；null 时用 ID 首字符占位 */
  avatar: string | null
}

const STORAGE_KEY = 'xcpc-helper:activity-profile'

const storage: Storage | null = typeof localStorage === 'undefined' ? null : localStorage

function load(): UserProfile {
  try {
    const raw = storage?.getItem(STORAGE_KEY)
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

const profile = reactive<UserProfile>(load())

watch(
  profile,
  (value) => {
    try {
      storage?.setItem(STORAGE_KEY, JSON.stringify(value))
    } catch {
      /* 头像超出 localStorage 配额时静默失败，内存态本次会话仍生效 */
    }
  },
  { deep: true },
)

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
