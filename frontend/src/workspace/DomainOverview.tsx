import { useMemo } from 'react'
import { IxButton } from '@siemens/ix-react'
import { domainOf, relationLabel, type TraceGraph, type TraceNode } from './types'
import { classifyNode } from './nodeAppearance'

const purpose: Record<string, string> = {
  AM: 'Architecture resources and their implementation links.', RM: 'Requirements, implementation traces and validation links.',
  CM: 'Change requests and their linked source evidence.', QM: 'Test definitions, execution records and provider outcomes.',
  TRS: 'Tracked resources, deletion state and imported change events.',
}
export default function DomainOverview({ graph, domain, onSelect, onConnections }: { graph: TraceGraph | null; domain: string; onSelect: (node: TraceNode) => void; onConnections: () => void }) {
  const summary = useMemo(() => {
    const resources = graph?.nodes.filter(node => domainOf(node) === domain) || []
    const ids = new Set(resources.map(node => node.id)), linked = new Set<string>()
    const predicates = new Map<string, number>()
    graph?.edges.forEach(edge => {
      if (!ids.has(edge.source) && !ids.has(edge.target)) return
      linked.add(edge.source); linked.add(edge.target)
      predicates.set(edge.type, (predicates.get(edge.type) || 0) + 1)
    })
    const types = new Map<string, { label: string; count: number }>()
    resources.forEach(node => { const type = classifyNode(node); types.set(type.key, { label: type.label, count: (types.get(type.key)?.count || 0) + 1 }) })
    return { resources, unlinked: resources.filter(node => !linked.has(node.id)), deleted: resources.filter(node => node.properties.deleted).length, types: [...types.values()], predicates: [...predicates].sort((a, b) => b[1] - a[1]) }
  }, [graph, domain])
  return <section className="source-context-panel" aria-label={`${domain} overview`}><p className="page-purpose">{purpose[domain] || 'Imported lifecycle evidence.'}</p>
    {!summary.resources.length ? <div className="empty-section"><h2>No imported {domain} resources</h2><p>Configure a provider or lifecycle manifest, then synchronize this source.</p><IxButton onClick={onConnections}>Configure connections</IxButton></div> : <>
      <div className="source-metrics"><span><b>{summary.resources.length}</b> resources</span><span><b>{summary.unlinked.length}</b> without explicit links</span><span><b>{summary.deleted}</b> deleted</span></div>
      <div className="domain-summary-grid"><section><h2>Resource types</h2><dl className="source-metric-list">{summary.types.map(type => <div key={type.label}><dt>{type.label}</dt><dd>{type.count}</dd></div>)}</dl></section>
        <section><h2>Relationships</h2><dl className="source-metric-list">{summary.predicates.slice(0, 8).map(([predicate, count]) => <div key={predicate}><dt title={predicate}>{relationLabel(predicate)}</dt><dd>{count}</dd></div>)}</dl>{!summary.predicates.length && <p>No explicit relationships imported.</p>}</section></div>
      {!!summary.unlinked.length && <section><h2>Resources to review</h2><p>These resources have no edges in this snapshot.</p><ul className="source-findings">{summary.unlinked.slice(0, 12).map(node => <li key={node.id}><button onClick={() => onSelect(node)}>{node.label}</button></li>)}</ul>{summary.unlinked.length > 12 && <small>Showing 12 of {summary.unlinked.length}; use Data grid for the full list.</small>}</section>}
    </>}
  </section>
}
