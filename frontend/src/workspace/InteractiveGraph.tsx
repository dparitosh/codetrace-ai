import { IxButton } from '@siemens/ix-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraphCanvas from './ForceGraphCanvas'
import type { ForceGraphActions } from './D3ForceGraph'
import type { ForceLayout } from './forceGraphModel'
import { Crosshair, Minus, Plus, Maximize2, RotateCcw, Layers, Search, Pause, Play, Pin } from 'lucide-react'
import { domainColors, domainOf, TraceGraph, TraceNode } from './types'
import { containmentDescendants, localContext, matchingNodes, revealContextRoot, visibleGraph } from './graphModel'
import type { TraversalDirection, RelationScope } from './graphModel'
import { nodeLegend, type NodeColorMode } from './nodeAppearance'

interface Props { graph: TraceGraph | null; selected: string | null; onSelect: (node: TraceNode | null) => void; busy: boolean; highlighted?: string[]; active?: boolean; domainFilter?: string; onDomainChange?: (domain: string) => void }
export default function InteractiveGraph({ graph, selected, onSelect, busy, highlighted, active = true, domainFilter, onDomainChange }: Props) {
  const engine = useRef<ForceGraphActions>(null)
  const [localDomain, setLocalDomain] = useState('ALL')
  const domain = domainFilter ?? localDomain
  const setDomain = (value: string) => { setLocalDomain(value); onDomainChange?.(value) }
  const [detail, setDetail] = useState(true)
  const [layout, setLayout] = useState<ForceLayout>('force')
  const [paused, setPaused] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false)
  const [pinOnDrag, setPinOnDrag] = useState(false)
  const [allLabels, setAllLabels] = useState(false)
  const [colorMode, setColorMode] = useState<NodeColorMode>('classification')
  const [direction, setDirection] = useState<TraversalDirection>('both')
  const [relationScope, setRelationScope] = useState<RelationScope>('all')
  const [query, setQuery] = useState('')
  const [searchLimit, setSearchLimit] = useState(12)
  useEffect(() => setSearchLimit(12), [query, graph])
  const [focus, setFocus] = useState<string | null>(null)
  const [focusDepth, setFocusDepth] = useState(1)
  const [collapsed, setCollapsed] = useState(new Set<string>())
  const limits = graph?.metadata.limits || { render_nodes: 400, render_edges: 1000 }
  const view = useMemo(() => graph ? visibleGraph(graph, domain, detail, limits.render_nodes, limits.render_edges,
    focus ? localContext(graph, focus, focusDepth, direction, relationScope) : undefined, collapsed, selected, relationScope) : null,
    [graph, domain, detail, focus, focusDepth, direction, relationScope, collapsed, selected, limits.render_nodes, limits.render_edges])
  const matches = useMemo(() => matchingNodes(graph, query, Infinity), [graph, query])
  const domains = useMemo(() => graph ? [...new Set(graph.nodes.map(domainOf))].filter(value => value !== 'EXTERNAL').sort() : [], [graph])
  const legend = useMemo(() => nodeLegend(view?.nodes || [], colorMode), [view, colorMode])
  useEffect(() => { setFocus(null); setQuery(''); setLocalDomain('ALL'); setCollapsed(new Set()); setFocusDepth(1) }, [graph])
  const options = useMemo(() => ({ layout, focus, direction, selected, paused: paused || !active, pinOnDrag, allLabels, highlighted, colorMode }), [layout, focus, direction, selected, paused, pinOnDrag, allLabels, highlighted, active, colorMode])
  const focusSelection = () => {
    if (!graph || !selected) return
    setDomain('ALL'); setCollapsed(current => revealContextRoot(graph, current, selected)); setFocus(selected)
  }
  const selectMatch = (node: TraceNode) => { onSelect(node); setDomain('ALL'); setCollapsed(new Set()); setFocus(node.id); setFocusDepth(1); setQuery('') }
  const canCollapse = !!(graph && selected && containmentDescendants(graph, selected).size)
  const toggleCollapse = () => {
    if (!selected) return
    setCollapsed(current => { const next = new Set(current); if (next.has(selected)) next.delete(selected); else next.add(selected); return next })
  }
  const expandResource = (node: TraceNode) => {
    if (!graph) return
    onSelect(node); setDomain('ALL')
    setCollapsed(current => { const next = revealContextRoot(graph, current, node.id); next.delete(node.id); return next })
    setFocusDepth(current => focus === node.id ? Math.min(6, current + 1) : 1)
    setFocus(node.id)
  }
  return <section className="graph-panel">
    <div className="graph-panel-header"><div><h2>Network <span className="count-badge">{graph?.nodes.length.toLocaleString() || 0}</span></h2></div>
      <div className="graph-toolbar"><label><input type="checkbox" checked={detail} onChange={event => setDetail(event.target.checked)} /> Show functions & variables</label>
        <IxButton variant="secondary" disabled={!canCollapse} onClick={toggleCollapse}>{selected && collapsed.has(selected) ? 'Expand children' : 'Collapse children'}</IxButton>
        <IxButton variant="secondary" disabled={!graph || !selected || (focus === selected && focusDepth >= 6)} onClick={() => { focusSelection(); setCollapsed(current => { const next = new Set(current); if (selected) next.delete(selected); return next }); setFocusDepth(current => focus === selected ? Math.min(6, current + 1) : 1) }}>Expand context</IxButton>
        <IxButton variant="tertiary" disabled={!graph} onClick={() => { setCollapsed(new Set()); setFocus(null); setFocusDepth(1); setDirection('both'); setRelationScope('all'); setDetail(true); setLayout('force'); setDomain('ALL'); engine.current?.releasePins(); onSelect(null) }}>Reset view</IxButton>
        <select aria-label="Graph layout" value={layout} onChange={event => setLayout(event.target.value as ForceLayout)}><option value="force">Force network</option><option value="hierarchy">Hierarchical force</option><option value="circle">Circular force</option><option value="concentric">Concentric</option><option value="grid">Grid</option></select>
      </div>
    </div>
    <section className="node-legend" aria-label="Node classification legend">
      <div className="node-legend-heading"><label>Color <select aria-label="Node color mode" value={colorMode} onChange={event => setColorMode(event.target.value as NodeColorMode)}><option value="classification">Classification</option><option value="domain">Lifecycle domain</option></select></label><small>Visible nodes by {colorMode === 'classification' ? 'type' : 'domain'}</small></div>
      <ul>{legend.map(item => <li key={item.key}><span className="classification-swatch" style={{ backgroundColor: item.color }} aria-hidden="true">{item.glyph}</span><span>{item.label}</span><b>{item.count}</b></li>)}</ul>
    </section>
    <details className="graph-advanced"><summary>Traversal & layout controls</summary>
    <div className="graph-traversal-bar">
      <label>Traverse <select aria-label="Traversal direction" value={direction} onChange={event => { setDirection(event.target.value as TraversalDirection); focusSelection() }}>
        <option value="both">Both directions</option><option value="outgoing">Downstream · outgoing</option><option value="incoming">Upstream · incoming</option>
      </select></label>
      <label>Context <select aria-label="Traversal relationships" value={relationScope} onChange={event => { setRelationScope(event.target.value as RelationScope); focusSelection() }}>
        <option value="all">All relationships</option><option value="hierarchy">Containment hierarchy</option><option value="evidence">Code & lifecycle evidence</option>
      </select></label>
      <label>Depth <select aria-label="Traversal depth" value={focusDepth} onChange={event => { setFocusDepth(Number(event.target.value)); focusSelection() }}>
        {[1, 2, 3, 4, 5, 6].map(value => <option key={value} value={value}>{value} {value === 1 ? 'hop' : 'hops'}</option>)}
      </select></label>
    </div>
    <div className="force-motion-controls">
      <IxButton variant="secondary" disabled={!graph} onClick={() => setPaused(value => !value)}><span className="ix-button-label">{paused ? <Play size={13} /> : <Pause size={13} />}{paused ? 'Resume motion' : 'Pause motion'}</span></IxButton>
      <IxButton variant="tertiary" disabled={!graph} onClick={() => { setPaused(false); engine.current?.reheat() }}>Reheat layout</IxButton>
      <IxButton variant={pinOnDrag ? 'primary' : 'secondary'} aria-pressed={pinOnDrag} onClick={() => setPinOnDrag(value => !value)}><span className="ix-button-label"><Pin size={13} />Pin after drag</span></IxButton>
      <IxButton variant="tertiary" disabled={!graph} onClick={() => engine.current?.releasePins()}>Release pins</IxButton>
      <IxButton variant="secondary" disabled={!graph || !highlighted?.length} onClick={() => { setDomain('ALL'); setCollapsed(new Set()); setFocus(highlighted![0]); setFocusDepth(2) }}>Explore highlighted context</IxButton>
      <IxButton variant={allLabels ? 'primary' : 'secondary'} aria-pressed={allLabels} onClick={() => setAllLabels(value => !value)}>{allLabels ? 'All labels' : 'Contextual labels'}</IxButton>
    </div>
    </details>
    <div className="graph-filter-bar"><div className="domain-filters"><IxButton variant={domain === 'ALL' ? 'primary' : 'secondary'} aria-pressed={domain === 'ALL'} onClick={() => { setDomain('ALL'); setFocus(null) }}>All domains</IxButton>
      {domains.map(value => <IxButton key={value} variant={domain === value ? 'primary' : 'secondary'} aria-pressed={domain === value} onClick={() => { setDomain(value); setFocus(null) }}><i style={{ background: domainColors[value] }} />{value}</IxButton>)}</div>
      <div className="graph-search"><Search size={14} /><input aria-label="Search graph resources" placeholder="Find a resource…" value={query} onChange={event => setQuery(event.target.value)} />
        {query && <div className="search-results">{matches.length ? matches.slice(0, searchLimit).map(node => <IxButton key={node.id} onClick={() => selectMatch(node)}><span>{node.label}</span><small>{node.type} · {node.properties.path || node.id}</small></IxButton>) : <p>No matching resource</p>}<p>Showing {Math.min(searchLimit, matches.length)} of {matches.length} matches</p>{matches.length > searchLimit && <IxButton onClick={() => setSearchLimit(current => current + 12)}>Show more matches</IxButton>}</div>}
      </div>
    </div>
    <div className="graph-canvas-wrap">
      <ForceGraphCanvas ref={engine} graph={graph} nodes={view?.nodes || []} edges={view?.edges || []} options={options} onSelect={onSelect} onExpand={expandResource} />
      {!graph && <div className="graph-empty"><div className="empty-graph-orbit"><Layers size={32} /></div><h3>Your connected view starts here.</h3><p>Select a managed source and synchronize its code and lifecycle evidence.</p><span>OSLC AM · RM · CM · QM · TRS</span></div>}
      {busy && <div className="graph-loading"><span className="pulse-dot" />Synchronizing source and lifecycle evidence…</div>}
      {focus && <IxButton className="focus-chip" onClick={() => setFocus(null)}><Crosshair size={13} />Focused context <RotateCcw size={12} /></IxButton>}
      <div className="canvas-controls"><IxButton variant="tertiary" aria-label="Zoom in" onClick={() => engine.current?.zoomBy(1.25)}><Plus size={16} /></IxButton>
        <IxButton variant="tertiary" aria-label="Zoom out" onClick={() => engine.current?.zoomBy(1 / 1.25)}><Minus size={16} /></IxButton>
        <IxButton variant="tertiary" aria-label="Fit graph" onClick={() => engine.current?.fit()}><Maximize2 size={16} /></IxButton>
        <IxButton variant="tertiary" aria-label="Focus selected context" disabled={!selected} onClick={focusSelection}><Crosshair size={16} /></IxButton></div>
      <div className="canvas-watermark"><span className="live-dot" />{view ? `${view.nodes.length} visible · ${view.edges.length} relationships · ${view.components} connected component${view.components === 1 ? '' : 's'}` : 'Awaiting source'}{view?.omitted ? ` · ${view.omitted} nodes omitted` : ''}{view?.omittedEdges ? ` · ${view.omittedEdges} relationships omitted` : ''}</div>
    </div>
    <details className="graph-help"><summary>Graph help & coverage</summary><p>Drag nodes to reshape, background to pan, scroll to zoom. Double-click or Shift+Enter to expand. Search covers the full snapshot.</p><p>{colorMode === 'classification' ? 'Fill and letter: type. Outer ring: domain.' : 'Fill: domain. Letter: type.'} Solid outline: selection; dashed: agent evidence; faded: deleted.</p>{graph && <p>{graph.nodes.filter(node => ['function', 'method'].includes(node.type)).length} functions/methods · {graph.nodes.filter(node => node.type === 'feature').length} features in snapshot. Features require explicit lifecycle artifacts and trace links.</p>}</details>
  </section>
}
