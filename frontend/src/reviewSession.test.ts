import { afterEach, describe, expect, it, vi } from 'vitest'

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const timing = { expires_in_seconds: 60, absolute_remaining_seconds: 120 }

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); vi.resetModules() })

describe('review session client', () => {
  it('publishes decisions so history and the active graph share review state', async () => {
    const updated = { id: 'graph', kind: 'graph', status: 'approved', result_digest: 'digest', revision: 1 }
    vi.stubGlobal('fetch', vi.fn(async (url, options) => {
      if (String(url).endsWith('/decision')) {
        expect(JSON.parse(options.body).result_digest).toBe('digest')
        return json(updated)
      }
      return json(String(url).endsWith('/session') && options?.method === 'POST' ? { token: 'session', ...timing } : timing)
    }))
    const api = await import('./reviewSession')
    await api.startSession()
    const listener = vi.fn()
    const unsubscribe = api.subscribeReviewChanges(listener)
    const result = await api.decideReview({ id: 'graph', sessionToken: 'session', result_digest: 'digest', revision: 0 } as any, 'approved', '')
    expect(listener).toHaveBeenCalledWith(result)
    unsubscribe()
    await api.decideReview({ ...result }, 'approved', '')
    expect(listener).toHaveBeenCalledTimes(1)
  })
  it('coalesces concurrent session creation', async () => {
    const fetch = vi.fn(async () => json({ token: 'one', ...timing }))
    vi.stubGlobal('fetch', fetch)
    const { startSession } = await import('./reviewSession')
    const values = await Promise.all([startSession(), startSession()])
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(values[0].token).toBe(values[1].token)
  })
  it('does not send approvals for a review from an older session', async () => {
    const fetch = vi.fn(async () => json({ token: 'new-session', ...timing }))
    vi.stubGlobal('fetch', fetch)
    const api = await import('./reviewSession')
    await api.startSession()
    await expect(api.decideReview({ id: 'old', sessionToken: 'old-session' } as any, 'approved', '')).rejects.toThrow('previous session')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('aborts hung requests at their deadline', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))
    const { requestJson } = await import('./reviewSession')
    const request = requestJson('/api/slow', {}, 2)
    const assertion = expect(request).rejects.toThrow('timed out')
    await vi.advanceTimersByTimeAsync(2000)
    await assertion
  })
  it('rejects approval after the local session deadline', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(async () => json({ token: 'one', ...timing })))
    const api = await import('./reviewSession')
    await api.startSession()
    await vi.advanceTimersByTimeAsync(61000)
    await expect(api.decideReview({ sessionToken: 'one' } as any, 'approved', '')).rejects.toThrow('Session expired')
  })
})
