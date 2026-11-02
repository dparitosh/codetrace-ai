import { afterEach, describe, expect, it, vi } from 'vitest'
import { agentTimeoutSeconds, mergeSnapshotReview } from './workspaceContext'
import type { ReviewRecord } from '../reviewSession'

const record = (id = 'one', token = 'session', digest = 'digest'): ReviewRecord => ({
  id, sessionToken: token, result_digest: digest, kind: 'graph', status: 'pending',
  revision: 0, created_at: '', audit: [], result: { nodes: [{ id: 'selected' }], edges: [], metadata: {} },
})
describe('shared snapshot review state', () => {
  it('preserves graph identity and exploration state when the decision changes', () => {
    const current = record()
    const updated = mergeSnapshotReview(current, { ...record(), status: 'approved', revision: 1 })
    expect(updated.status).toBe('approved')
    expect(updated.revision).toBe(1)
    expect(updated.result).toBe(current.result)
  })
  it('uses new graph data for a new snapshot or session', () => {
    const current = record()
    for (const incoming of [record('two'), record('one', 'new-session'), record('one', 'session', 'different')]) {
      expect(mergeSnapshotReview(current, incoming)).toBe(incoming)
    }
  })
})


afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

describe('agent timeout before AI configuration arrives', () => {
  const catalog = { ai: { timeout_seconds: 45, agent_timeout_seconds: 125 }, settings: { request_timeout_seconds: 120 } } as any
  it('uses the total agent budget while the profile is loading or unavailable', () => {
    expect(agentTimeoutSeconds(catalog)).toBe(125)
    expect(agentTimeoutSeconds(catalog, 200)).toBe(200)
    expect(agentTimeoutSeconds({ ...catalog, ai: { timeout_seconds: 45 } })).toBe(125)
  })
  it('does not abort a valid answer after the shorter per-call timeout', async () => {
    vi.useFakeTimers()
    let finish: (response: Response) => void = () => undefined
    let signal: AbortSignal | undefined
    vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise<Response>((resolve, reject) => {
      finish = resolve; signal = options.signal
      options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))
    const { requestJson } = await import('../reviewSession')
    const result = requestJson('/api/v1/workspace/agent/run', {}, agentTimeoutSeconds(catalog))
    await vi.advanceTimersByTimeAsync(60000)
    expect(signal?.aborted).toBe(false)
    finish(new Response(JSON.stringify({ answer: 'Observed [E1]' }), { headers: { 'Content-Type': 'application/json' } }))
    await expect(result).resolves.toMatchObject({ answer: 'Observed [E1]' })
  })
})
