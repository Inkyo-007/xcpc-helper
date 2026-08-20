/** 热力图档位映射（纯函数）。着色规则见 docs/design/activity/conventions.md：
 * 0 无提交；1 有提交但无 AC（最低档）；2–5 按 AC 数分桶（1 / 2–3 / 4–5 / ≥6）。
 */

export type HeatLevel = 0 | 1 | 2 | 3 | 4 | 5

export function heatLevel(submissions: number, solved: number): HeatLevel {
  if (submissions <= 0) return 0
  if (solved <= 0) return 1
  if (solved <= 1) return 2
  if (solved <= 3) return 3
  if (solved <= 5) return 4
  return 5
}

export const HEAT_LEVEL_COUNT = 6
