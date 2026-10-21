import { describe, expect, it } from 'vitest'
import { mergeSnapshotReview } from './workspaceContext'
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
