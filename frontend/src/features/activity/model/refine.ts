/** 精细化同步耗时预估（纯函数，vitest 覆盖）。
 *
 * 每条 UNAC 记录一次详情请求，节奏为平台限流间隔（洛古 5s/条）。
 */

/** 预估文案：约 X 分钟 / 约 X 小时（< 1 分钟按 1 分钟计） */
export function estimateRefineDuration(total: number, intervalSeconds = 5): string {
  if (total <= 0) return '无需精化'
  const minutes = Math.ceil((total * intervalSeconds) / 60)
  if (minutes < 60) return `约 ${minutes} 分钟`
  const hours = Math.round((minutes / 60) * 10) / 10
  return `约 ${hours} 小时`
}
