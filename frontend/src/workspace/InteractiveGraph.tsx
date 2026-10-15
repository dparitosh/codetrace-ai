import { IxButton } from '@siemens/ix-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import cytoscape, { Core } from 'cytoscape'
import { Crosshair, Minus, Plus, Maximize2, RotateCcw, Layers, Search } from 'lucide-react'
import { domainColors, domainOf, relationLabel, TraceGraph, TraceNode } from './types'
import { containmentDescendants, localContext, matchingNodes, revealContextRoot, visibleGraph } from './graphModel'
import type { TraversalDirection, RelationScope } from './graphModel'

interface Props { graph: TraceGraph | null; selected: string | null; onSelect: (node: TraceNode | null) => void; busy: boolean }
export default function InteractiveGraph({ graph, selected, onSelect, busy }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const cy = useRef<Core | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  const [domain, setDomain] = useState('ALL')
  const [detail, setDetail] = useState(false)
  const [layout, setLayout] = useState('breadthfirst')
  const [direction, setDirection] = useState<TraversalDirection>('both')
  const [relationScope, setRelationScope] = useState<RelationScope>('all')
  const [query, setQuery] = useState('')
  const [searchLimit, setSearchLimit] = useState(12)
  useEffect(() => setSearchLimit(12), [query, graph])
  const [focus, setFocus] = useState<string | null>(null)
  const [focusDepth, setFocusDepth] = useState(1)
  const [collapsed, setCollapsed] = useState(new Set<string>())
  const layoutKey = layout === 'breadthfirst' ? `${layout}:${focus || ''}:${direction}:${relationScope}` : layout
  const [palette, setPalette] = useState({ text: '#526175', surface: '#ffffff', edge: '#b7c4d2', primary: '#3fb8aa' })
  useEffect(() => {
    const updatePalette = () => {
      const theme = getComputedStyle(document.documentElement)
      setPalette({ text: theme.getPropertyValue('--theme-color-std-text').trim() || '#526175',
        surface: theme.getPropertyValue('--theme-color-1').trim() || '#ffffff',
        edge: theme.getPropertyValue('--theme-color-soft-text').trim() || '#b7c4d2',
        primary: theme.getPropertyValue('--theme-color-primary').trim() || '#3fb8aa' })
    }
    updatePalette()
    const observer = new MutationObserver(updatePalette)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-ix-theme', 'data-ix-color-schema'] })
    return () => observer.disconnect()
  }, [])
  const viewport = useRef<{ graph: TraceGraph; layout: string; zoom: number; pan: { x: number; y: number }; positions: Map<string, { x: number; y: number }> } | null>(null)
  const limits = graph?.metadata.limits || { render_nodes: 400, render_edges: 1000 }
  const view = useMemo(() => graph ? visibleGraph(graph, domain, detail, limits.render_nodes, limits.render_edges,
    focus ? localContext(graph, focus, focusDepth, direction, relationScope) : undefined, collapsed, selected, relationScope) : null,
    [graph, domain, detail, focus, focusDepth, direction, relationScope, collapsed, selected, limits.render_nodes, limits.render_edges])
  const matches = useMemo(() => matchingNodes(graph, query, Infinity), [graph, query])
  const domains = useMemo(() => graph ? [...new Set(graph.nodes.map(domainOf))].filter(value => value !== 'EXTERNAL').sort() : [], [graph])
  useEffect(() => { setFocus(null); setQuery(''); setDomain('ALL'); setCollapsed(new Set()); setFocusDepth(1) }, [graph])
  useEffect(() => {
    if (!container.current || !view || !graph) return
    const nodeMap = new Map(graph.nodes.map(node => [node.id, node]))
    const previous = viewport.current
    const reuseLayout = previous?.graph === graph && previous.layout === layoutKey
      && view.nodes.every(node => previous.positions.has(node.id))
    const engine = cytoscape({
      container: container.current, pixelRatio: Math.min(window.devicePixelRatio, 2), wheelSensitivity: 0.2,
      minZoom: 0.08, maxZoom: 4, selectionType: 'single',
      elements: [
        ...view.nodes.map(node => ({ data: { id: node.id, label: node.label.length > 26 ? node.label.slice(0, 24) + '…' : node.label,
          color: domainColors[domainOf(node)] || '#93a1b3',
          weight: ['repository', 'package'].includes(node.type) ? 48 : 36 } })),
        ...view.edges.map((edge, index) => ({ data: { id: 'edge-' + index, source: edge.source, target: edge.target,
          label: relationLabel(edge.type), lifecycle: edge.properties.origin === 'lifecycle_assertion' ? 1 : 0 } })),
      ],
      style: [
        { selector: 'node', style: { 'background-color': 'data(color)', 'shape': 'ellipse', width: 'data(weight)', height: 'data(weight)',
          'border-width': 2, 'border-color': palette.surface, 'label': 'data(label)', 'font-size': 10,
          'font-family': 'Siemens Sans, system-ui, sans-serif', 'color': palette.text, 'text-valign': 'bottom', 'text-margin-y': 9,
          'text-background-color': palette.surface, 'text-background-opacity': 0.9, 'text-background-padding': '3px' } },
        { selector: 'edge', style: { width: 1.2, 'line-color': palette.edge, 'target-arrow-color': palette.edge,
          'target-arrow-shape': 'triangle', 'arrow-scale': 0.65, 'curve-style': 'bezier', opacity: 0.65 } },
        { selector: 'edge[lifecycle = 1]', style: { 'line-color': palette.primary, 'target-arrow-color': palette.primary, width: 2, opacity: 0.85 } },
        { selector: 'node.focused-resource', style: { 'border-color': palette.primary, 'border-width': 4,
          width: (node: cytoscape.NodeSingular) => Number(node.data('weight')) * 1.2,
          height: (node: cytoscape.NodeSingular) => Number(node.data('weight')) * 1.2 } },
        { selector: '.faded', style: { opacity: 0.12 } },
        { selector: '.context-edge', style: { label: 'data(label)', 'font-size': 9, 'color': palette.text, 'text-rotation': 'autorotate',
          'text-background-color': palette.surface, 'text-background-opacity': 1, 'text-background-padding': '3px', width: 2, opacity: 1 } },
      ],
      layout: reuseLayout ? { name: 'preset', positions: Object.fromEntries(previous.positions), fit: false }
        : { name: layout, directed: true, roots: focus && direction === 'outgoing' ? [focus] : undefined,
          spacingFactor: 1.25, avoidOverlap: true, animate: false, padding: 55, randomize: true, nodeRepulsion: 13000,
          idealEdgeLength: 100, gravity: 0.35, numIter: 600 } as cytoscape.LayoutOptions,
    })
    cy.current = engine
    if (reuseLayout) {
      engine.zoom(previous.zoom); engine.pan(previous.pan)
    }
    engine.on('tap', 'node', event => {
      const node = nodeMap.get(event.target.id())
      if (node) onSelectRef.current(node)
    })
    engine.on('tap', event => { if (event.target === engine) onSelectRef.current(null) })
    const resize = new ResizeObserver(() => engine.resize())
    resize.observe(container.current)
    return () => {
      const positions = viewport.current?.graph === graph && viewport.current.layout === layoutKey
        ? new Map(viewport.current.positions) : new Map<string, { x: number; y: number }>()
      engine.nodes().forEach(node => { positions.set(node.id(), { ...node.position() }) })
      viewport.current = { graph, layout: layoutKey, zoom: engine.zoom(), pan: engine.pan(), positions }
      resize.disconnect(); engine.destroy(); cy.current = null
    }
  }, [view, graph, layout, layoutKey, focus, direction, palette])
  useEffect(() => {
    const engine = cy.current
    if (!engine) return
    engine.batch(() => {
      engine.elements().removeClass('faded context-edge focused-resource').unselect()
      if (!selected) return
      const node = engine.getElementById(selected)
      if (node.empty()) return
      const context = node.closedNeighborhood()
      engine.elements().not(context).addClass('faded')
      context.edges().addClass('context-edge'); node.addClass('focused-resource')
    })
  }, [selected, view, layout, palette])
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
  return <section className="graph-panel">
    <div className="graph-panel-header"><div><span className="eyebrow">CONNECTED EVIDENCE</span><h2>Lifecycle graph <span className="count-badge">{graph?.nodes.length || 0}</span></h2></div>
      <div className="graph-toolbar"><IxButton variant="secondary" onClick={() => setDetail(value => !value)}><span className="ix-button-label"><Layers size={14} />{detail ? 'Symbol view' : 'Architecture view'}</span></IxButton>
        <IxButton variant="secondary" disabled={!canCollapse} onClick={toggleCollapse}>{selected && collapsed.has(selected) ? 'Expand children' : 'Collapse children'}</IxButton>
        <IxButton variant="secondary" disabled={!graph || !selected || (focus === selected && focusDepth >= 6)} onClick={() => { focusSelection(); setCollapsed(current => { const next = new Set(current); if (selected) next.delete(selected); return next }); setFocusDepth(current => focus === selected ? Math.min(6, current + 1) : 1) }}>Expand context</IxButton>
        <IxButton variant="tertiary" disabled={!graph} onClick={() => { setCollapsed(new Set()); setFocus(null); setFocusDepth(1); setDirection('both'); setRelationScope('all'); setLayout('breadthfirst'); setDomain('ALL'); onSelect(null) }}>Reset view</IxButton>
        <select aria-label="Graph layout" value={layout} onChange={event => setLayout(event.target.value)}><option value="circle">Circular</option><option value="cose">Organic layout</option><option value="breadthfirst">Hierarchy</option><option value="concentric">Concentric</option><option value="grid">Grid</option></select>
      </div>
    </div>
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
      <small>{focus ? 'Showing the selected resource and its bounded context.' : 'Select a resource to traverse its context.'}</small>
    </div>
    <div className="graph-filter-bar"><div className="domain-filters"><IxButton variant={domain === 'ALL' ? 'primary' : 'secondary'} aria-pressed={domain === 'ALL'} onClick={() => { setDomain('ALL'); setFocus(null) }}>All domains</IxButton>
      {domains.map(value => <IxButton key={value} variant={domain === value ? 'primary' : 'secondary'} aria-pressed={domain === value} onClick={() => { setDomain(value); setFocus(null) }}><i style={{ background: domainColors[value] }} />{value}</IxButton>)}</div>
      <div className="graph-search"><Search size={14} /><input aria-label="Search graph resources" placeholder="Find a resource…" value={query} onChange={event => setQuery(event.target.value)} />
        {query && <div className="search-results">{matches.length ? matches.slice(0, searchLimit).map(node => <IxButton key={node.id} onClick={() => selectMatch(node)}><span>{node.label}</span><small>{node.type} · {node.properties.path || node.id}</small></IxButton>) : <p>No matching resource</p>}<p>Showing {Math.min(searchLimit, matches.length)} of {matches.length} matches</p>{matches.length > searchLimit && <IxButton onClick={() => setSearchLimit(current => current + 12)}>Show more matches</IxButton>}</div>}
      </div>
    </div>
    <div className="graph-canvas-wrap">
      <div className="graph-canvas" ref={container} aria-label="Interactive lifecycle graph canvas" />
      {!graph && <div className="graph-empty"><div className="empty-graph-orbit"><Layers size={32} /></div><h3>Your connected view starts here.</h3><p>Select a managed source and synchronize its code and lifecycle evidence.</p><span>OSLC AM · RM · CM · QM · TRS</span></div>}
      {busy && <div className="graph-loading"><span className="pulse-dot" />Synchronizing source and lifecycle evidence…</div>}
      {focus && <IxButton className="focus-chip" onClick={() => setFocus(null)}><Crosshair size={13} />Focused context <RotateCcw size={12} /></IxButton>}
      <div className="canvas-controls"><IxButton variant="tertiary" aria-label="Zoom in" onClick={() => cy.current?.zoom((cy.current?.zoom() || 1) * 1.25)}><Plus size={16} /></IxButton>
        <IxButton variant="tertiary" aria-label="Zoom out" onClick={() => cy.current?.zoom((cy.current?.zoom() || 1) / 1.25)}><Minus size={16} /></IxButton>
        <IxButton variant="tertiary" aria-label="Fit graph" onClick={() => cy.current?.fit(undefined, 45)}><Maximize2 size={16} /></IxButton>
        <IxButton variant="tertiary" aria-label="Focus selected context" disabled={!selected} onClick={focusSelection}><Crosshair size={16} /></IxButton></div>
      <div className="canvas-watermark"><span className="live-dot" />{view ? `${view.nodes.length} visible · ${view.edges.length} relationships` : 'Awaiting source'}{view?.omitted ? ` · ${view.omitted} nodes omitted` : ''}{view?.omittedEdges ? ` · ${view.omittedEdges} relationships omitted` : ''}</div>
    </div>
    <div className="graph-panel-footer"><span>Drag to explore. Scroll to zoom. Select a node to inspect its evidence.</span><span>{graph ? 'Snapshot ' + String(graph.metadata.snapshot_id || '').slice(0, 8) : 'No snapshot'}</span></div>
  </section>
}
