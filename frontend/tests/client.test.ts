import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, asError, optional, pages, request } from '../src/api/client'
import { api } from '../src/api/console'
import type { Gate, Workflow } from '../src/types/models'

afterEach(() => vi.unstubAllGlobals())
describe('unified HTTP client', () => {
  it('retains backend error code, message, request_id and details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'VERSION_CONFLICT', message: 'stale', request_id: 'req-42', details: { expected: 1 } } }), { status: 409 })))
    await expect(request('/example')).rejects.toMatchObject({ code: 'VERSION_CONFLICT', requestId: 'req-42', status: 409, details: { expected: 1 } })
  })
  it('handles a proxy HTML error with request header fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502, headers: { 'X-Request-ID': 'proxy-request' } })))
    await expect(request('/example')).rejects.toMatchObject({ code: 'HTTP_502', requestId: 'proxy-request' })
  })
  it('does not swallow network or validation errors as missing optional artifacts', async () => {
    await expect(optional(Promise.reject(new ApiError('NOT_FOUND', 'missing', null, 404)))).resolves.toBeNull()
    await expect(optional(Promise.reject(new ApiError('VALIDATION_ERROR', 'invalid', 'r', 422)))).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
    expect(asError(new TypeError('fetch failed')).code).toBe('NETWORK_ERROR')
  })
  it('loads more than one page rather than hiding old versions or gates', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(Array.from({ length: 200 }, (_, i) => i)))).mockResolvedValueOnce(new Response('[200]'))
    vi.stubGlobal('fetch', fetch)
    expect(await pages<number>('/versions')).toHaveLength(201)
    expect(fetch.mock.calls[1]?.[0]).toBe('/api/v1/versions?limit=200&offset=200')
  })
  it('HumanGate sends only server contract fields with the displayed version; never retries', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'VERSION_CONFLICT', message: 'stale' } }), { status: 409 }))
    vi.stubGlobal('fetch', fetch)
    await expect(api.decide({ id: 'wf', state_version: 12 } as Workflow, { id: 'gate', artifact_version: 2 } as Gate, 'MODIFY', '  保留原始反馈  ', 'event')).rejects.toBeInstanceOf(ApiError)
    expect(fetch).toHaveBeenCalledTimes(1)
    const call = fetch.mock.calls[0]
    expect(call?.[0]).toBe('/api/v1/human-gates/gate/decision')
    expect(JSON.parse(call?.[1].body)).toEqual({ event_id: 'event', expected_state_version: 12, expected_artifact_version: 2, decision: 'MODIFY', reason: '  保留原始反馈  ' })
  })
})
