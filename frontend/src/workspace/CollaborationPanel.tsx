import { useEffect, useMemo, useState } from 'react'
import { IxButton } from '@siemens/ix-react'
import { collaborationRequest, ReviewRecord } from '../reviewSession'
import { Catalog, relationLabel, TraceGraph, TraceNode } from './types'
import { matchingNodes } from './graphModel'

interface Proposal { id: string; review_id: string; source: string; target: string; predicate: string; status: string; version: number; audit?: { action: string; message?: string; note?: string }[] }

function ResourcePicker({ label, nodes, value, onChange }: { label: string; nodes: TraceNode[]; value: string; onChange: (id: string) => void }) {
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(50)
  useEffect(() => setLimit(50), [query])
  const matches = useMemo(() => query.trim() ? matchingNodes({ nodes, edges: [], metadata: {} }, query, Infinity) : nodes, [nodes, query])
  const shown = matches.slice(0, limit)
  const current = nodes.find(node => node.id === value)
  return <label className="collaboration-picker">{label}
    <input aria-label={'Search ' + label} placeholder="Search labels, identifiers or paths" value={query} onChange={event => setQuery(event.target.value)} />
    <select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
      <option value="">Select a resource</option>
      {current && !shown.some(node => node.id === value) && <option value={value}>{current.label} · {current.id}</option>}
      {shown.map(node => <option key={node.id} value={node.id}>{node.label} · {node.properties.identifier || node.properties.path || node.id}</option>)}
    </select>
    <small>{Math.min(limit, matches.length)} of {matches.length} matches</small>
    {matches.length > limit && <IxButton variant="tertiary" onClick={() => setLimit(currentLimit => currentLimit + 50)}>Show more resources</IxButton>}
  </label>
}

export default function CollaborationPanel({ review, graph, catalog, selected }: { review: ReviewRecord; graph: TraceGraph; catalog: Catalog | null; selected: TraceNode | null }) {
  const request = <T,>(path: string, body?: unknown) => collaborationRequest<T>(path, review.sessionToken, body, catalog?.settings.collaboration_timeout_seconds)
  const [source, setSource] = useState('')
  const [target, setTarget] = useState(selected?.id || '')
  const [predicate, setPredicate] = useState('')
  const [note, setNote] = useState('')
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [pageSize, setPageSize] = useState(100)
  const [hasMore, setHasMore] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const nodes = useMemo(() => graph.nodes.filter(node => !node.properties.deleted), [graph])
  const writable = useMemo(() => new Set(catalog?.providers.filter(provider => provider.allow_writes).map(provider => provider.id)), [catalog])
  const sources = useMemo(() => nodes.filter(node => writable.has(node.properties.provider_id)), [nodes, writable])
  const providerId = nodes.find(node => node.id === source)?.properties.provider_id
  useEffect(() => { if (selected) setTarget(selected.id) }, [selected])
  useEffect(() => {
    let cancelled = false
    setBusy(true)
    const load = async () => {
      const items: Proposal[] = []
      for (let offset = 0; offset < pageSize; offset += 100) {
        const page = await collaborationRequest<Proposal[]>(`proposals?offset=${offset}&limit=100`, review.sessionToken)
        items.push(...page)
        if (page.length < 100) break
      }
      if (!cancelled) { setProposals(items); setHasMore(items.length >= pageSize) }
    }
    load().catch(cause => { if (!cancelled) setError(String(cause)) }).finally(() => { if (!cancelled) setBusy(false) })
    return () => { cancelled = true }
  }, [review.sessionToken, pageSize, refresh])
  const run = async (action: () => Promise<Proposal>) => {
    if (busy) return
    setBusy(true); setError('')
    try {
      const item = await action()
      setProposals(current => [item, ...current.filter(existing => existing.id !== item.id)])
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Collaboration failed') }
    finally { setBusy(false) }
  }
  return <section className="collaboration-panel" aria-label="ALM link collaboration">
    <h3>ALM contextual links</h3>
    <p>Prepare a link from an approved graph, review the exact endpoints, then approve and apply it. Remote writes use a captured ETag; uncertain outcomes require reconciliation.</p>
    {!sources.length && <p>Enable writes for a centrally configured provider and synchronize its resources to propose links.</p>}
    <ResourcePicker label="Source resource" nodes={sources} value={source} onChange={setSource} />
    <ResourcePicker label="Target resource" nodes={nodes} value={target} onChange={setTarget} />
    <label>Relationship<select aria-label="Link predicate" value={predicate} onChange={event => setPredicate(event.target.value)}><option value="">Select a relationship</option>{catalog?.link_predicates?.map(value => <option key={value} value={value}>{relationLabel(value)} · {value}</option>)}</select></label>
    <IxButton disabled={busy || review.status !== 'approved' || !providerId || !target || !predicate} onClick={() => run(() => request<Proposal>('proposals', { review_id: review.id, provider_id: providerId, source, predicate, target }))}>Prepare link proposal</IxButton>
    <label>Decision note<textarea aria-label="Link decision note" maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /></label>
    <IxButton disabled={busy} onClick={() => { setError(''); setRefresh(current => current + 1) }}>Refresh link proposals</IxButton>
    {proposals.filter(item => item.review_id === review.id).map(item => <article key={item.id} className="link-proposal">
      <strong>{item.status} · {relationLabel(item.predicate)}</strong><p>{item.source} → {item.target}</p>
      {item.status === 'pending' && <>{(['approved', 'rejected'] as const).map(action => <IxButton key={action} disabled={busy} onClick={() => run(() => request<Proposal>(`proposals/${item.id}/decision`, { version: item.version, action, note }))}>{action === 'approved' ? 'Approve link' : 'Reject link'}</IxButton>)}</>}
      {item.status === 'approved' && <IxButton disabled={busy} onClick={() => run(() => request<Proposal>(`proposals/${item.id}/apply`, { version: item.version }))}>Apply approved link to ALM</IxButton>}
      {['unknown', 'conflict', 'not_observed', 'applying'].includes(item.status) && <IxButton disabled={busy} onClick={() => run(() => request<Proposal>(`proposals/${item.id}/reconcile`, { version: item.version }))}>Reconcile remote state</IxButton>}
      <details><summary>Link audit history</summary>{item.audit?.map((event, index) => <p key={index}>{event.action} {event.message} {event.note}</p>)}</details>
    </article>)}
    {hasMore && <IxButton disabled={busy} onClick={() => setPageSize(current => current + 100)}>Load older proposals</IxButton>}
    {error && <p role="alert">{error}</p>}
  </section>
}
