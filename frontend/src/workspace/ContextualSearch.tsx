import { useEffect, useRef, useState } from 'react'
import { IxButton } from '@siemens/ix-react'
import { aiRequest, workspaceRequest } from '../reviewSession'
import type { ReviewRecord } from '../reviewSession'
import type { TraceGraph, TraceNode } from './types'
import type { AIProfile } from './AISettings'

interface SearchResult { node_id: string; label: string; domain: string; lexical_score: number; semantic_score: number | null }
interface Result { results: SearchResult[]; query: string; mode: string; semantic_nodes: number; candidate_nodes: number; warning?: string; limitations: string[] }

export default function ContextualSearch({ review, graph, onSelect, onHighlight }: { review: ReviewRecord | null; graph: TraceGraph | null; onSelect: (node: TraceNode) => void; onHighlight: (ids: string[]) => void }) {
  const [query, setQuery] = useState(''), [semantic, setSemantic] = useState(true)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const generation = useRef(0)
  useEffect(() => {
    const requestCounter = generation
    requestCounter.current++; setResult(null); setBusy(false); setError('')
    return () => { requestCounter.current++ }
  }, [review?.id, review?.sessionToken])
  const search = async () => {
    if (!review || !query.trim() || busy) return
    const current = ++generation.current
    setBusy(true); setError(''); setResult(null)
    try {
      const profile = await aiRequest<AIProfile>('config')
      const answer = await workspaceRequest<Result>('search', { review_id: review.id, query, semantic, limit: 20 }, profile.request_timeout_seconds || 125, review.sessionToken)
      if (current !== generation.current) return
      setResult(answer); onHighlight(answer.results.map(node => node.node_id))
    } catch (cause) { if (current === generation.current) setError(cause instanceof Error ? cause.message : 'Search failed') }
    finally { if (current === generation.current) setBusy(false) }
  }
  return <section className="contextual-search" aria-label="Contextual graph search">
    <form onSubmit={event => { event.preventDefault(); search() }}>
      <label>Contextual graph search<input aria-label="Contextual graph search" value={query} maxLength={1500} onChange={event => setQuery(event.target.value)} placeholder="Describe a requirement, behavior, failure or dependency…" disabled={!review || busy} /></label>
      <label><input type="checkbox" checked={semantic} onChange={event => setSemantic(event.target.checked)} />Nomic / hybrid retrieval</label>
      <IxButton type="submit" disabled={!review || busy || !query.trim()}>{busy ? 'Retrieving context…' : 'Search graph'}</IxButton>
    </form>
    {result && <><p>{result.mode} search for “{result.query}” · {result.results.length} results · embeddings compared across {result.semantic_nodes} of {result.candidate_nodes} candidates</p>
      {result.warning && <p role="status">{result.warning}</p>}
      <div className="contextual-results">{result.results.map(item => <button key={item.node_id} onClick={() => { const node = graph?.nodes.find(node => node.id === item.node_id); if (node) onSelect(node) }}><strong>{item.label}</strong><small>{item.domain} · keyword {item.lexical_score.toFixed(2)}{item.semantic_score !== null ? ` · cosine ${item.semantic_score.toFixed(3)}` : ''}</small></button>)}</div>
      {!result.results.length && <p>No matching resources in this bounded search.</p>}
      <small>{result.limitations.join(' ')}</small><IxButton variant="tertiary" onClick={() => { setResult(null); onHighlight([]) }}>Clear search highlights</IxButton>
    </>}
    {error && <p role="alert">{error}</p>}
  </section>
}
