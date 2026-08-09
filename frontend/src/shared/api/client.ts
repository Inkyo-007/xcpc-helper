/** fetch 封装：统一 baseURL 与错误规范化（与后端全局异常结构对齐）。 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string }
}

/** 把非 2xx 响应规范化为 ApiError（错误体非 JSON 时保留兜底文案）。 */
export async function toApiError(resp: Response, fallback: string): Promise<ApiError> {
  let code = 'unknown'
  let message = fallback
  try {
    const body = (await resp.json()) as ErrorBody
    code = body.error?.code ?? code
    message = body.error?.message ?? message
  } catch {
    // 非 JSON 错误体时保留默认信息
  }
  return new ApiError(resp.status, code, message)
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError(0, 'network_error', '无法连接后端服务，请确认后端已启动')
  }
  if (!resp.ok) {
    throw await toApiError(resp, `请求失败（${resp.status}）`)
  }
  // 204 No Content（如 DELETE 成功）没有响应体，直接返回 undefined
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}
