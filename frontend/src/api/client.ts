export class ApiError extends Error {
  constructor(public code: string, message: string, public requestId: string | null = null,
    public status = 0, public details: unknown = null) { super(message) }
}

export function asError(value: unknown): ApiError {
  return value instanceof ApiError ? value : new ApiError('NETWORK_ERROR',
    '无法连接服务，请检查 Backend 和网络后手动刷新。')
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' ? value as Record<string, unknown> : {}
}

const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
// This console uses a same-origin proxy; browser configuration cannot redirect story data.
if (!/^\/(?!\/)[\w/-]+$/.test(base)) throw new Error('VITE_API_BASE_URL must be a relative API path')

export async function request<T>(path: string, options: { body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const response = await fetch(base.replace(/\/$/, '') + path, {
    method: options.body === undefined ? 'GET' : 'POST',
    headers: options.body === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
  })
  let data: unknown
  try { data = await response.json() } catch { data = null }
  if (!response.ok) {
    const error = record(record(data).error)
    throw new ApiError(typeof error.code === 'string' ? error.code : `HTTP_${response.status}`,
      typeof error.message === 'string' ? error.message : '服务未返回可用结果，请检查 Backend。',
      typeof error.request_id === 'string' ? error.request_id : response.headers.get('X-Request-ID'),
      response.status, error.details)
  }
  if (data === null) throw new ApiError('INVALID_RESPONSE', '服务响应不是有效 JSON。', response.headers.get('X-Request-ID'))
  return data as T
}

export async function optional<T>(result: Promise<T>): Promise<T | null> {
  try { return await result } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export async function pages<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const results: T[] = []
  for (let offset = 0; ; offset += 200) {
    const page = await request<T[]>(`${path}?limit=200&offset=${offset}`, { signal })
    results.push(...page)
    if (page.length < 200) return results
  }
}
