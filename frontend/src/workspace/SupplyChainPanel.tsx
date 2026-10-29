import { lazy, Suspense, useMemo, useRef, useState } from 'react'
import { approvedSnapshot, type ReviewRecord } from '../reviewSession'
import type { TraceGraph, TraceNode } from './types'
import { dependencyAnalysis, dependencyIndex, lineagePreview, lineageSvg, type SupplyMode } from './supplyChainModel'
import ForceGraphCanvas from './ForceGraphCanvas'
import type { ForceGraphActions } from './D3ForceGraph'
import type { ForceLayout } from './forceGraphModel'
import './supplyChain.css'
const GraphDataTable = lazy(() => import('./GraphDataTable'))

export default function SupplyChainPanel({ graph, review }: { graph: TraceGraph | null; review: ReviewRecord | null }) {
  // Remount on snapshot change in Workspace; selection can never bleed into another review.
  const index = useMemo(() => dependencyIndex(graph || { nodes: [], edges: [], metadata: {} }), [graph])
  const application = [...index.nodes.values()].find(node => node.type === 'repository')?.id || ''
  const [start, setStart] = useState(application)
  const [target, setTarget] = useState('')
  const [mode, setMode] = useState<SupplyMode>('dependencies')
  const [tab, setTab] = useState<'graph' | 'table'>('graph')
  const [selected, setSelected] = useState<string | null>(null)
  const [layout, setLayout] = useState<ForceLayout>('hierarchy')
  const [paused, setPaused] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const engine = useRef<ForceGraphActions>(null)
  const analysis = useMemo(() => dependencyAnalysis(index, mode, start, target), [index, mode, start, target])
  const preview = useMemo(() => lineagePreview(index, analysis), [index, analysis])
  const resources = useMemo(() => analysis.ids.map(id => index.nodes.get(id)!), [index, analysis])
  const options = useMemo(() => ({ layout, focus: mode === 'inventory' ? null : start,
    direction: mode === 'dependents' ? 'incoming' as const : 'outgoing' as const, selected,
    paused: paused || tab !== 'graph', pinOnDrag: true, allLabels: true, labelSize: 20, highlighted: mode === 'path' ? analysis.path : [] }),
  [layout, start, mode, selected, paused, tab, analysis])
  const componentCount = [...index.nodes.values()].filter(node => node.type === 'sbom_component').length
  const unresolved = graph?.metadata.sbom?.unresolved_dependencies || []
  const selectedNode = selected ? index.nodes.get(selected) : null
  const noRootEvidence = !!start && index.nodes.get(start)?.type === 'repository' && !index.outgoing.get(start)?.length
  const inspect = (node: TraceNode | null) => setSelected(node?.id || null)
  const download = async (format: 'svg' | 'json') => {
    if (!review || !graph || exporting) return
    setExporting(true); setError('')
    try {
      const approved = await approvedSnapshot(review)
      const approvedIndex = dependencyIndex(approved.result as TraceGraph)
      const result = dependencyAnalysis(approvedIndex, mode, start, target)
      const visible = lineagePreview(approvedIndex, result)
      const title = `Supply-chain ${mode} · ${visible.nodes.length}/${result.ids.length} resources · snapshot ${String(approved.result.metadata.snapshot_id).slice(0, 12)}`
      const body = format === 'svg' ? lineageSvg(visible.nodes, visible.edges, title) : JSON.stringify({
        snapshot: approved.result.metadata.snapshot_id, result_digest: approved.result_digest, mode, start, target,
        scope: 'Recorded depends_on edges only; includes development dependencies when present; not runtime or vulnerability evidence.',
        limitations: approved.result.metadata.sbom?.limitations || [],
        sbom_evidence: approved.result.metadata.sbom || {},
        nodes: result.ids.map(id => approvedIndex.nodes.get(id)), edges: result.edges, path: result.path,
      }, null, 2)
      const url = URL.createObjectURL(new Blob([body], { type: format === 'svg' ? 'image/svg+xml' : 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `supply-chain-lineage.${format}`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Lineage export failed') }
    finally { setExporting(false) }
  }
  if (!graph) return <section className="plain-panel"><p>Synchronize a managed source to explore its supply chain.</p></section>
  if (!componentCount) return <section className="plain-panel"><h2>{unresolved.length ? 'No resolved SBOM components' : 'No SBOM inventory'}</h2><ResolutionGaps entries={unresolved} /><p>Configure sbom_path for CycloneDX/SPDX JSON, or sbom_lockfiles for npm lockfiles v2/v3 in the managed source. Then synchronize. Folder uploads do not import lockfiles.</p></section>
  return <section className="supply-chain" aria-label="Supply-chain lineage">
    <p>Follow recorded package dependencies. Arrows point from consumer to dependency; inventory membership and source-code containment are excluded.</p>
    <ResolutionGaps entries={unresolved} />
    <div className="supply-controls">
      <label>Explore<select value={mode} onChange={event => { setMode(event.target.value as SupplyMode); setSelected(null) }}>
        <option value="dependencies">Dependencies · downstream</option><option value="dependents">Dependents · upstream</option>
        <option value="path">Shortest dependency path</option><option value="inventory">Full inventory</option>
      </select></label>
      {mode !== 'inventory' && <ResourcePicker label={mode === 'path' ? 'Root / consumer' : 'Starting resource'} nodes={[...index.nodes.values()]} value={start} onChange={value => { setStart(value); setSelected(null) }} />}
      {mode === 'path' && <ResourcePicker label="Target component" nodes={[...index.nodes.values()].filter(node => node.type === 'sbom_component')} value={target} onChange={setTarget} />}
    </div>
    {noRootEvidence && mode !== 'dependents' && mode !== 'inventory' && <p className="workspace-alert caution" role="status">Application dependency roots are not recorded in this snapshot. Select a component as the starting resource, or synchronize with explicit root dependencies. Inventory membership cannot establish a path.</p>}
    {mode === 'path' && <p role="status">{!start || !target ? 'Choose a root and target to find their lineage.' : analysis.found
      ? `${analysis.path.length - 1} dependency hop(s). One shortest path is shown; alternatives may exist.`
      : 'No directed dependency path is recorded between these resources. This does not prove the package is unused.'}</p>}
    <div className="supply-summary" role="status">{mode === 'inventory' ? `${componentCount} components in inventory` : `${Math.max(0, analysis.ids.length - (analysis.ids.length ? 1 : 0))} ${mode === 'path' ? 'hops on selected path' : 'reachable resources, excluding start'}`} · {analysis.edges.length} recorded dependency edges</div>
    <details><summary>Evidence scope & limitations</summary><p>Reachability is evaluated across the complete retained snapshot, without the graph explorer’s hop cap. Results are only as complete as the imported SBOM or lockfiles. A dependency path does not prove runtime use, exploitability, or vulnerability.</p>
      <p>Advisory lookup: {graph.metadata.sbom?.advisory_lookup?.status || 'not recorded'}. {graph.metadata.sbom?.advisory_lookup?.checked_components || 0} components checked; {graph.metadata.sbom?.advisory_lookup?.matches?.length || 0} recorded matches. Disabled, unavailable or partial lookup does not establish that packages are vulnerability-free.</p>
      {(graph.metadata.sbom?.limitations || []).map((item: string) => <p key={item}>{item}</p>)}
      {index.dangling > 0 && <p>{index.dangling} dependency edges with missing endpoints were excluded.</p>}
    </details>
    <div className="supply-toolbar"><div role="group" aria-label="Lineage view"><button aria-pressed={tab === 'graph'} onClick={() => setTab('graph')}>Lineage graph</button><button aria-pressed={tab === 'table'} onClick={() => setTab('table')}>Data table · AG Grid</button></div>
      <button disabled={!analysis.ids.length || review?.status !== 'approved' || exporting} onClick={() => download('svg')}>Export diagram (SVG preview)</button>
      <button disabled={!analysis.ids.length || review?.status !== 'approved' || exporting} onClick={() => download('json')}>Export complete results (JSON)</button>
      {review?.status !== 'approved' && <small>Approve this snapshot in Review center to export.</small>}
    </div>
    {error && <p role="alert">{error}</p>}
    {tab === 'graph' ? <>
      <div className="supply-toolbar"><label>Layout<select value={layout} onChange={event => setLayout(event.target.value as ForceLayout)}><option value="hierarchy">Hierarchical lineage</option><option value="force">Force network</option></select></label>
        <button onClick={() => engine.current?.fit()} disabled={!preview.nodes.length}>Fit</button><button aria-label="Zoom in" onClick={() => engine.current?.zoomBy(1.2)}>+</button><button aria-label="Zoom out" onClick={() => engine.current?.zoomBy(0.8)}>−</button>
        <button aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? 'Resume layout' : 'Pause layout'}</button>
        <span>Application nodes are blue; package nodes are brown. Select a node to inspect.</span></div>
      <p>{preview.nodes.length} of {analysis.ids.length} resources displayed · {preview.edges.length} of {analysis.edges.length} edges{preview.truncated ? '. Preview is limited to 200 nodes / 500 edges; use Data table or JSON for complete results.' : ''}</p>
      {!!preview.nodes.length && <div className="supply-canvas"><ForceGraphCanvas ref={engine} graph={graph} nodes={preview.nodes} edges={preview.edges} options={options} onSelect={inspect} onExpand={inspect} /></div>}
    </> : <Suspense fallback={<p role="status">Loading dependency table…</p>}><GraphDataTable graph={{ ...graph, nodes: resources, edges: analysis.edges }} resources={resources} onSelect={inspect} /></Suspense>}
    {selectedNode && <section className="plain-panel" aria-label="Selected supply-chain resource"><h3>{selectedNode.label}</h3><dl><dt>Component identity</dt><dd>{String(selectedNode.properties.purl || selectedNode.properties.ref || selectedNode.id)}</dd><dt>Evidence</dt><dd>{String(selectedNode.properties.origin || 'Managed source')}</dd></dl>
      <button onClick={() => { setStart(selectedNode.id); setMode('dependencies'); setSelected(null) }}>Explore dependencies</button>
      <button onClick={() => { setStart(selectedNode.id); setMode('dependents'); setSelected(null) }}>Explore dependents</button>
      {mode !== 'inventory' && <button onClick={() => { if (mode === 'dependents') { setTarget(start); setStart(selectedNode.id) } else setTarget(selectedNode.id); setMode('path'); setSelected(null) }}>Show lineage path</button>}
      <button onClick={() => setSelected(null)}>Close inspector</button></section>}
    {mode === 'path' && analysis.found && <details><summary>Ordered path · {analysis.path.length} resources</summary><p>The first 200 steps are shown here; export JSON for longer paths.</p><ol>{analysis.path.slice(0, 200).map(id => <li key={id}><button onClick={() => setSelected(id)}>{index.nodes.get(id)?.label}</button></li>)}</ol></details>}
  </section>
}

function ResolutionGaps({ entries }: { entries: { name: string; kind: string; source: string; lockfile: string }[] }) {
  if (!entries.length) return null
  return <div className="supply-resolution"><p className="workspace-alert caution" role="status">Dependency lineage is incomplete: {entries.length} declared dependencies could not be resolved. Optional entries may be omitted for this platform or install scope.</p>
    <details><summary>Unresolved dependency evidence</summary><ul>{entries.slice(0, 20).map((entry, i) => <li key={i}>{entry.name} · {entry.kind} · {entry.source} · {entry.lockfile}</li>)}</ul>
      {entries.length > 20 && <p>Showing 20 of {entries.length}. All entries are retained in the approved snapshot and JSON export.</p>}</details></div>
}

function ResourcePicker({ label, nodes, value, onChange }: { label: string; nodes: TraceNode[]; value: string; onChange: (value: string) => void }) {
  const [query, setQuery] = useState('')
  const matches = nodes.filter(node => `${node.label} ${node.properties.purl || ''} ${node.properties.ref || ''}`.toLowerCase().includes(query.toLowerCase()))
  const choices = matches.slice(0, 200)
  const current = nodes.find(node => node.id === value)
  if (current && !choices.some(node => node.id === current.id)) choices.unshift(current)
  return <div className="supply-picker"><label>Filter {label.toLowerCase()}<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Name, version, purl or lockfile…" /></label>
    <label>{label}<select value={value} onChange={event => onChange(event.target.value)}><option value="">Choose a resource</option>{choices.map(node => <option key={node.id} value={node.id}>{node.label} · {String(node.properties.ref || node.type)}</option>)}</select></label>
    {matches.length > 200 && <small>Showing 200 of {matches.length} matches. Refine the filter.</small>}
  </div>
}
