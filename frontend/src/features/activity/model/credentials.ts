/** 手动粘贴凭据的解析（纯函数，vitest 覆盖）。
 *
 * 接受两种常见粘贴形态，提取 cookie 平台所需的字段：
 * 1. JSON 对象：{"_uid": "...", "__client_id": "..."}（可嵌套在 cookies 键下）；
 * 2. Cookie 头整串："_uid=...; __client_id=...; 其他=..."（浏览器复制）。
 * 所需字段任一缺失或输入无法识别时返回 null（调用方提示重新粘贴）。
 */

import type { AccountCredentials } from '@/features/activity/types'

export function parseCredentialInput(
  input: string,
  requiredKeys: string[],
): AccountCredentials | null {
  const text = input.trim()
  if (!text || requiredKeys.length === 0) return null
  const found = text.startsWith('{') ? parseJsonForm(text) : parseCookieHeader(text)
  if (!found) return null
  const cookies: Record<string, string> = {}
  for (const key of requiredKeys) {
    const value = found[key]?.trim()
    if (!value) return null
    cookies[key] = value
  }
  return { cookies }
}

/** JSON 形态：字段在顶层或 cookies 键下均可 */
function parseJsonForm(text: string): Record<string, string> | null {
  try {
    const data: unknown = JSON.parse(text)
    if (!data || typeof data !== 'object') return null
    const obj = data as Record<string, unknown>
    const nested = obj.cookies
    const merged: Record<string, string> = {}
    if (nested && typeof nested === 'object') {
      for (const [k, v] of Object.entries(nested as Record<string, unknown>)) {
        if (typeof v === 'string') merged[k] = v
      }
    }
    for (const [k, v] of Object.entries(obj)) {
      if (typeof v === 'string') merged[k] = v
    }
    return merged
  } catch {
    return null
  }
}

/** Cookie 头形态：分号分隔的 key=value 对 */
function parseCookieHeader(text: string): Record<string, string> | null {
  if (!text.includes('=')) return null
  const pairs: Record<string, string> = {}
  for (const part of text.split(';')) {
    const eq = part.indexOf('=')
    if (eq <= 0) continue
    const key = part.slice(0, eq).trim()
    const value = part.slice(eq + 1).trim()
    if (key) pairs[key] = value
  }
  return Object.keys(pairs).length > 0 ? pairs : null
}
