import { useEffect, useMemo, useRef, useState } from 'react'
import cytoscape, { Core } from 'cytoscape'
import { Crosshair, Minus, Plus, Maximize2, RotateCcw, Layers, Search } from 'lucide-react'
import { domainColors, domainOf, relationLabel, TraceGraph, TraceNode } from './types'
import { containmentDescendants, localContext, matchingNodes, visibleGraph } from './graphModel'

interface Props { graph: TraceGraph | null; selected: string | null; onSelect: (node: TraceNode | null) => void; busy: boolean }
export default function InteractiveGraph({ graph, selected, onSelect, busy }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const cy = useRef<Core | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  const [domain, setDomain] = useState('ALL')
  const [detail, setDetail] = useState(false)
  const [layout, setLayout] = useState('cose')
  const [query, setQuery] = useState('')
  const [focus, setFocus] = useState<string | null>(null)
  const [focusDepth, setFocusDepth] = useState(1)
  const [collapsed, setCollapsed] = useState(new Set<string>())
  const viewport = useRef<{ graph: TraceGraph; layout: string; zoom: number; pan: { x: number; y: number }; positions: Map<string, { x: number; y: number }> } | null>(null)
  const limits = graph?.metadata.limits || { render_nodes: 400, render_edges: 1000 }
  const view = useMemo(() => graph ? visibleGraph(graph, domain, detail, limits.render_nodes, limits.render_edges,
    focus ? localContext(graph, focus, focusDepth) : undefined, collapsed, selected) : null,
    [graph, domain, detail, focus, focusDepth, collapsed, selected, limits.render_nodes, limits.render_edges])
  const matches = useMemo(() => matchingNodes(graph, query), [graph, query])
  const domains = useMemo(() => graph ? [...new Set(graph.nodes.map(domainOf))].filter(value => value !== 'EXTERNAL').sort() : [], [graph])
  useEffect(() => { setFocus(null); setQuery(''); setDomain('ALL'); setCollapsed(new Set()); setFocusDepth(1) }, [graph])
  useEffect(() => {
    if (!container.current || !view || !graph) return
    const nodeMap = new Map(graph.nodes.map(node => [node.id, node]))
    const engine = cytoscape({
      container: container.current, pixelRatio: Math.min(window.devicePixelRatio, 2), wheelSensitivity: 0.2,
      minZoom: 0.08, maxZoom: 4, selectionType: 'single',
      elements: [
        ...view.nodes.map(node => ({ data: { id: node.id, label: node.label.length > 26 ? node.label.slice(0, 24) + '…' : node.label,
          color: domainColors[domainOf(node)] || '#93a1b3', shape: domainOf(node) === 'CODE' ? 'round-rectangle' : 'ellipse',
          weight: ['repository', 'package'].includes(node.type) ? 48 : 36 } })),
        ...view.edges.map((edge, index) => ({ data: { id: 'edge-' + index, source: edge.source, target: edge.target,
          label: relationLabel(edge.type), lifecycle: edge.properties.origin === 'lifecycle_assertion' ? 1 : 0 } })),
      ],
      style: [
        { selector: 'node', style: { 'background-color': 'data(color)', 'shape': node => node.data('shape') as cytoscape.Css.NodeShape, width: 'data(weight)', height: 'data(weight)',
          'border-width': 5, 'border-color': '#ffffff', 'label': 'data(label)', 'font-size': 10,
          'font-family': 'Inter, system-ui, sans-serif', 'color': '#526175', 'text-valign': 'bottom', 'text-margin-y': 9,
          'text-background-color': '#f9fbfc', 'text-background-opacity': 0.9, 'text-background-padding': '3px' } },
        { selector: 'edge', style: { width: 1.2, 'line-color': '#cbd4df', 'target-arrow-color': '#b7c4d2',
          'target-arrow-shape': 'triangle', 'arrow-scale': 0.65, 'curve-style': 'bezier', opacity: 0.65 } },
        { selector: 'edge[lifecycle = 1]', style: { 'line-color': '#3fb8aa', 'target-arrow-color': '#3fb8aa', width: 2, opacity: 0.85 } },
        { selector: ':selected', style: { 'border-color': '#132f45', 'border-width': 3 } },
        { selector: '.faded', style: { opacity: 0.12 } },
        { selector: '.context-edge', style: { label: 'data(label)', 'font-size': 9, 'color': '#3e6870', 'text-rotation': 'autorotate',
          'text-background-color': '#fff', 'text-background-opacity': 1, 'text-background-padding': '3px', width: 2, opacity: 1 } },
      ],
      layout: { name: layout, animate: false, padding: 55, randomize: true, nodeRepulsion: 13000,
        idealEdgeLength: 100, gravity: 0.35, numIter: 600 } as cytoscape.LayoutOptions,
    })
    cy.current = engine
    const previous = viewport.current
    if (previous?.graph === graph && previous.layout === layout) {
      engine.nodes().forEach(node => { const position = previous.positions.get(node.id()); if (position) node.position(position) })
      engine.zoom(previous.zoom); engine.pan(previous.pan)
    }
    engine.on('tap', 'node', event => {
      const node = nodeMap.get(event.target.id())
      if (node) onSelectRef.current(node)
    })
    engine.on('tap', event => { if (event.target === engine) onSelectRef.current(null) })
    const resize = new ResizeObserver(() => engine.resize())
    resize.observe(container.current)
    return () => { viewport.current = { graph, layout, zoom: engine.zoom(), pan: engine.pan(), positions: new Map(engine.nodes().map(node => [node.id(), { ...node.position() }])) }; resize.disconnect(); engine.destroy(); cy.current = null }
  }, [view, graph, layout])
  useEffect(() => {
    const engine = cy.current
    if (!engine) return
    engine.batch(() => {
      engine.elements().removeClass('faded context-edge').unselect()
      if (!selected) return
      const node = engine.getElementById(selected)
      if (node.empty()) return
      const context = node.closedNeighborhood()
      engine.elements().not(context).addClass('faded')
      context.edges().addClass('context-edge'); node.select()
    })
  }, [selected, view, layout])
  const selectMatch = (node: TraceNode) => { onSelect(node); setCollapsed(new Set()); setFocus(node.id); setFocusDepth(1); setQuery('') }
  const canCollapse = !!(graph && selected && containmentDescendants(graph, selected).size)
  const toggleCollapse = () => {
    if (!selected) return
    setCollapsed(current => { const next = new Set(current); if (next.has(selected)) next.delete(selected); else next.add(selected); return next })
  }
  return <section className="graph-panel">
    <div className="graph-panel-header"><div><span className="eyebrow">CONNECTED EVIDENCE</span><h2>Lifecycle graph <span className="count-badge">{graph?.nodes.length || 0}</span></h2></div>
      <div className="graph-toolbar"><button className={detail ? 'toggle active' : 'toggle'} onClick={() => setDetail(value => !value)}><Layers size={14} />{detail ? 'Symbol view' : 'Architecture view'}</button>
        <button disabled={!canCollapse} onClick={toggleCollapse}>{selected && collapsed.has(selected) ? 'Expand children' : 'Collapse children'}</button>
        <button disabled={!graph || !selected} onClick={() => { setCollapsed(new Set()); setFocus(selected); setFocusDepth(current => focus === selected ? current + 1 : 1) }}>Expand context</button>
        <button disabled={!graph} onClick={() => { setCollapsed(new Set()); setFocus(null); setDomain('ALL'); onSelect(null) }}>Reset view</button>
        <select aria-label="Graph layout" value={layout} onChange={event => setLayout(event.target.value)}><option value="cose">Organic layout</option><option value="breadthfirst">Hierarchy</option><option value="concentric">Concentric</option><option value="grid">Grid</option></select>
      </div>
    </div>
    <div className="graph-filter-bar"><div className="domain-filters"><button className={domain === 'ALL' ? 'active' : ''} onClick={() => { setDomain('ALL'); setFocus(null) }}>All domains</button>
      {domains.map(value => <button key={value} className={domain === value ? 'active' : ''} onClick={() => { setDomain(value); setFocus(null) }}><i style={{ background: domainColors[value] }} />{value}</button>)}</div>
      <div className="graph-search"><Search size={14} /><input aria-label="Search graph resources" placeholder="Find a resource…" value={query} onChange={event => setQuery(event.target.value)} />
        {query && <div className="search-results">{matches.length ? matches.map(node => <button key={node.id} onClick={() => selectMatch(node)}><span>{node.label}</span><small>{node.type}</small></button>) : <p>No matching resource</p>}</div>}
      </div>
    </div>
    <div className="graph-canvas-wrap">
      <div className="graph-canvas" ref={container} aria-label="Interactive lifecycle graph canvas" />
      {!graph && <div className="graph-empty"><div className="empty-graph-orbit"><Layers size={32} /></div><h3>Your connected view starts here.</h3><p>Select a managed source and synchronize its code and lifecycle evidence.</p><span>OSLC AM · RM · CM · QM · TRS</span></div>}
      {busy && <div className="graph-loading"><span className="pulse-dot" />Synchronizing source and lifecycle evidence…</div>}
      {focus && <button className="focus-chip" onClick={() => setFocus(null)}><Crosshair size={13} />Focused context <RotateCcw size={12} /></button>}
      <div className="canvas-controls"><button aria-label="Zoom in" onClick={() => cy.current?.zoom((cy.current?.zoom() || 1) * 1.25)}><Plus size={16} /></button>
        <button aria-label="Zoom out" onClick={() => cy.current?.zoom((cy.current?.zoom() || 1) / 1.25)}><Minus size={16} /></button>
        <button aria-label="Fit graph" onClick={() => cy.current?.fit(undefined, 45)}><Maximize2 size={16} /></button>
        <button aria-label="Focus selected context" disabled={!selected} onClick={() => setFocus(selected)}><Crosshair size={16} /></button></div>
      <div className="canvas-watermark"><span className="live-dot" />{view ? `${view.nodes.length} visible · ${view.edges.length} relationships` : 'Awaiting source'}{view?.omitted ? ` · ${view.omitted} nodes omitted` : ''}{view?.omittedEdges ? ` · ${view.omittedEdges} relationships omitted` : ''}</div>
    </div>
    <div className="graph-panel-footer"><span>Drag to explore. Scroll to zoom. Select a node to inspect its evidence.</span><span>{graph ? 'Snapshot ' + String(graph.metadata.snapshot_id || '').slice(0, 8) : 'No snapshot'}</span></div>
  </section>
}
