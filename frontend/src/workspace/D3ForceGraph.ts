import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type Simulation } from 'd3-force'
import { select, type Selection } from 'd3-selection'
import { drag, dragEnable, type D3DragEvent } from 'd3-drag'
import { zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from 'd3-zoom'
import { domainColors, domainOf, relationLabel, type TraceGraph, type TraceNode } from './types'
import { forceEdgePath, forceEdgeLabelPoint, layoutTargets, reconcileForceEdges, reconcileForceNodes, rebindForceNodes, type ForceEdge, type ForceLayout, type ForceNode } from './forceGraphModel'
import type { TraversalDirection } from './graphModel'
import { classifyNode, nodeFill, nodeGlyphColor, type NodeColorMode } from './nodeAppearance'
import './forceGraph.css'

export interface ForceGraphOptions {
  layout: ForceLayout; focus: string | null; direction: TraversalDirection
  selected: string | null; paused: boolean; pinOnDrag: boolean; allLabels: boolean
  highlighted?: string[]
  colorMode?: NodeColorMode
  labelSize?: number
}
export interface ForceGraphActions { fit: () => void; zoomBy: (factor: number) => void; reheat: () => void; releasePins: () => void }
type Group = Selection<SVGGElement, unknown, null, undefined>
let nextInstance = 0

/** Owns only the SVG subtree and mutable simulation copies, never React state. */
export class D3ForceGraph implements ForceGraphActions {
  private svg: Selection<SVGSVGElement, unknown, null, undefined>
  private viewport: Group
  private edgeLayer: Group
  private edgeLabels: Group
  private nodeLayer: Group
  private simulation: Simulation<ForceNode, ForceEdge>
  private zoomBehavior: ZoomBehavior<SVGSVGElement, unknown>
  private transform: ZoomTransform = zoomIdentity
  private nodes: ForceNode[] = []
  private edges: ForceEdge[] = []
  private cache = new Map<string, ForceNode>()
  private graph: TraceGraph | null = null
  private options: ForceGraphOptions | null = null
  private appearanceDirty = true
  private hovered: string | null = null
  private hoveredEdge: string | null = null
  private width = 1
  private height = 1
  private fitted = false
  private destroyed = false
  private activeWindow: Window | null = null
  private resizeObserver: ResizeObserver
  private markerPrefix = 'd3-force-' + ++nextInstance
  private nodeElements?: Selection<SVGGElement, ForceNode, SVGGElement, unknown>
  private edgeElements?: Selection<SVGPathElement, ForceEdge, SVGGElement, unknown>
  private labelElements?: Selection<SVGTextElement, ForceEdge, SVGGElement, unknown>

  constructor(private container: HTMLDivElement, private onSelect: (node: TraceNode | null) => void, private onExpand: (node: TraceNode) => void) {
    this.svg = select(container).append('svg').attr('class', 'd3-force-svg').attr('role', 'group')
      .attr('aria-label', 'Dynamic D3 force graph. Select a resource; drag to move it. Double-click or Shift+Enter to expand context.')
    const definitions = this.svg.append('defs')
    for (const kind of ['normal', 'lifecycle', 'context']) {
      definitions.append('marker').attr('id', this.markerPrefix + '-' + kind).attr('viewBox', '0 -4 9 8')
        .attr('refX', 8).attr('refY', 0).attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
        .append('path').attr('d', 'M0,-4L8,0L0,4Z').attr('class', 'd3-arrow-' + kind)
    }
    this.viewport = this.svg.append('g').attr('class', 'd3-viewport')
    this.edgeLayer = this.viewport.append('g').attr('class', 'd3-edges')
    this.edgeLabels = this.viewport.append('g').attr('class', 'd3-edge-labels').attr('aria-hidden', 'true')
    this.nodeLayer = this.viewport.append('g').attr('class', 'd3-nodes')
    this.simulation = forceSimulation<ForceNode>([]).stop().alphaDecay(.045).velocityDecay(.35)
      .on('tick.render', () => this.draw())
    this.zoomBehavior = zoom<SVGSVGElement, unknown>().scaleExtent([.025, 4]).extent(() => [[0, 0], [this.width, this.height]])
      .on('zoom.graph', event => { this.transform = event.transform; this.viewport.attr('transform', this.transform.toString()); this.drawLabels() })
    this.svg.call(this.zoomBehavior).on('dblclick.zoom', null)
      .on('click.graph', event => { if (event.target === this.svg.node()) this.onSelect(null) })
      .on('keydown.graph', event => { if (event.key === 'Escape') this.onSelect(null) })
    this.resizeObserver = new ResizeObserver(() => this.resize())
    this.resizeObserver.observe(container)
    this.resize()
  }

  private resize() {
    const bounds = this.container.getBoundingClientRect()
    if (!bounds.width || !bounds.height) return
    const dx = (bounds.width - this.width) / 2, dy = (bounds.height - this.height) / 2
    this.width = bounds.width; this.height = bounds.height
    this.svg.attr('viewBox', `0 0 ${this.width} ${this.height}`)
    if (!this.fitted) this.fit()
    else this.svg.call(this.zoomBehavior.transform, zoomIdentity.translate(this.transform.x + dx, this.transform.y + dy).scale(this.transform.k))
  }

  update(graph: TraceGraph | null, nodes: TraceNode[], edges: TraceGraph['edges'], options: ForceGraphOptions) {
    const freshGraph = graph !== this.graph
    const previous = this.options
    const priorNodes = new Set(this.nodes.map(node => node.id)), priorEdges = new Set(this.edges.map(edge => edge.id))
    if (freshGraph) { this.simulation.stop(); this.cache.clear(); this.fitted = false; this.hovered = null; this.hoveredEdge = null }
    this.graph = graph; this.options = options; this.appearanceDirty = true
    this.nodes = reconcileForceNodes(this.cache, nodes, edges)
    this.edges = reconcileForceEdges(this.nodes, edges)
    const changed = freshGraph || this.nodes.length !== priorNodes.size || this.edges.length !== priorEdges.size
      || this.nodes.some(node => !priorNodes.has(node.id)) || this.edges.some(edge => !priorEdges.has(edge.id))
    const layoutChanged = !previous || previous.layout !== options.layout || previous.focus !== options.focus || previous.direction !== options.direction
    this.join()
    if (!this.nodes.length) { this.simulation.stop().nodes([]); this.simulation.force('links', null); this.draw(); return }
    if (changed || layoutChanged) {
      const targets = layoutTargets(this.nodes, this.edges, options.layout, options.focus, options.direction)
      if (freshGraph && options.layout !== 'force') this.nodes.forEach(node => { const target = targets.get(node.id)!; node.x = target.x; node.y = target.y })
      // Remove the old link force before rebinding nodes: hidden endpoints must
      // never keep receiving force, nor refer to an obsolete node-array index.
      rebindForceNodes(this.simulation, this.nodes)
        .force('links', forceLink<ForceNode, ForceEdge>(this.edges).id(node => node.id).distance(options.layout === 'hierarchy' ? 155 : 110)
          .strength(edge => edge.source === edge.target ? 0 : options.layout === 'force' ? .25 : .045))
        .force('charge', forceManyBody<ForceNode>().strength(options.layout === 'force' ? -420 : -120).distanceMax(1800))
        .force('collision', forceCollide<ForceNode>().radius(node => node.radius + 20).iterations(2))
        .force('x', forceX<ForceNode>(node => targets.get(node.id)!.x).strength(options.layout === 'force' ? .035 : .35))
        .force('y', forceY<ForceNode>(node => targets.get(node.id)!.y).strength(options.layout === 'hierarchy' ? .8 : options.layout === 'force' ? .035 : .35))
    }
    // Fit settled positions, rather than the initial spiral or cached positions
    // from a different projection (which can leave the network off-screen).
    if (changed || layoutChanged) this.simulation.alpha(.65).tick(70)
    if (options.paused) {
      this.simulation.stop()
    } else if (changed || layoutChanged || previous?.paused) this.simulation.alpha(.65).alphaTarget(0).restart()
    this.draw()
    if (!this.fitted || changed || layoutChanged) this.fit()
  }

  private join() {
    this.edgeElements = this.edgeLayer.selectAll<SVGPathElement, ForceEdge>('path').data(this.edges, edge => edge.id).join('path')
      .attr('class', 'd3-edge').attr('data-edge-id', edge => edge.id)
      .on('mouseenter.graph', (_event, edge) => { this.hoveredEdge = edge.id; this.appearanceDirty = true; this.draw() })
      .on('mouseleave.graph', () => { this.hoveredEdge = null; this.appearanceDirty = true; this.draw() })
    this.edgeElements.selectAll('title').remove()
    this.edgeElements.append('title').text(edge => `${edge.source.resource.label} → ${edge.resource.type} → ${edge.target.resource.label}`)
    this.labelElements = this.edgeLabels.selectAll<SVGTextElement, ForceEdge>('text').data(this.edges, edge => edge.id).join('text')
      .text(edge => relationLabel(edge.resource.type))
    this.nodeElements = this.nodeLayer.selectAll<SVGGElement, ForceNode>('g.d3-node').data(this.nodes, node => node.id).join(enter => {
      const group = enter.append('g').attr('class', 'd3-node').attr('tabindex', 0).attr('role', 'button')
      group.append('circle').attr('class', 'd3-domain-ring').attr('fill', 'none')
      group.append('circle').attr('class', 'd3-node-disc')
      group.append('text').attr('class', 'd3-node-glyph').attr('text-anchor', 'middle').attr('dy', '.35em').attr('aria-hidden', 'true')
      group.append('circle').attr('class', 'd3-pin').attr('r', 3)
      group.append('text').attr('class', 'd3-node-label').attr('text-anchor', 'middle').attr('aria-hidden', 'true')
      group.append('title')
      return group
    }).attr('data-node-id', node => node.id).attr('data-classification', node => classifyNode(node.resource).key)
      .attr('data-domain', node => domainOf(node.resource))
      .classed('is-deleted', node => !!node.resource.properties.deleted)
      .attr('aria-label', node => `${node.resource.label} · ${domainOf(node.resource)} · ${classifyNode(node.resource).label}${node.resource.properties.deleted ? ' · deleted' : ''}`)
      .on('click.graph', (event, node) => { event.stopPropagation(); this.onSelect(node.resource) })
      .on('dblclick.graph', (event, node) => { event.stopPropagation(); this.onExpand(node.resource) })
      .on('mouseenter.graph', (_event, node) => { this.hovered = node.id; this.appearanceDirty = true; this.draw() })
      .on('mouseleave.graph', () => { this.hovered = null; this.appearanceDirty = true; this.draw() })
      .on('focus.graph', (_event, node) => { this.hovered = node.id; this.appearanceDirty = true; this.draw() })
      .on('blur.graph', () => { this.hovered = null; this.appearanceDirty = true; this.draw() })
      .on('keydown.graph', (event: KeyboardEvent, node) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); if (event.shiftKey) this.onExpand(node.resource); else this.onSelect(node.resource) }
      })
    this.nodeElements.select<SVGCircleElement>('circle.d3-node-disc').attr('r', node => node.radius)
      .attr('fill', node => nodeFill(node.resource, this.options?.colorMode))
    this.nodeElements.select<SVGCircleElement>('circle.d3-domain-ring').attr('r', node => node.radius + 4)
      .attr('stroke', node => domainColors[domainOf(node.resource)] || domainColors.EXTERNAL)
      .attr('display', this.options?.colorMode === 'domain' ? 'none' : null)
    this.nodeElements.select('text.d3-node-glyph').text(node => classifyNode(node.resource).glyph)
      .style('fill', node => node.resource.properties.deleted ? 'var(--ct-text, #203643)' : nodeGlyphColor(node.resource, this.options?.colorMode))
    this.nodeElements.select<SVGCircleElement>('circle.d3-pin').attr('cx', node => node.radius * .7).attr('cy', node => -node.radius * .7)
    this.nodeElements.select('title').text(node => `${node.resource.label}\n${classifyNode(node.resource).label} · ${domainOf(node.resource)}${node.resource.properties.deleted ? ' · Deleted resource' : ''}\n${node.resource.properties.path || node.id}\nDouble-click or Shift+Enter to expand context.`)
    const labelSize = this.options?.labelSize || 11
    this.nodeElements.select<SVGTextElement>('text.d3-node-label').style('font-size', `${labelSize}px`).each(function (node) {
      const label = node.resource.type === 'file' ? String(node.resource.properties.path || node.resource.label.replace(/^file:/, '')).split(/[\\/]/).pop()! : node.resource.label
      const lines = label.length <= 19 ? [label] : [label.slice(0, 19), label.slice(19, 36) + (label.length > 36 ? '…' : '')]
      select(this).selectAll('tspan').data(lines).join('tspan').attr('x', 0).attr('dy', (_line, index) => index ? '1.15em' : 0).text(line => line)
      select(this).attr('y', node.radius + 15)
    })
    this.nodeElements.call(drag<SVGGElement, ForceNode>().container(() => this.viewport.node()!).subject((_event, node) => node)
      .clickDistance(5)
      .on('start.graph', (event: D3DragEvent<SVGGElement, ForceNode, ForceNode>, node) => {
        if (this.destroyed) return
        this.activeWindow = event.sourceEvent.view || null
        event.sourceEvent.stopPropagation()
        node.fx = node.x; node.fy = node.y; this.appearanceDirty = true
        if (!event.active && !this.options?.paused) this.simulation.alphaTarget(.15).restart()
      })
      .on('drag.graph', (event, node) => {
        if (this.destroyed) return
        node.x = node.fx = event.x; node.y = node.fy = event.y
        this.draw()
      })
      .on('end.graph', (event, node) => {
        if (this.destroyed) return
        this.activeWindow = null
        if (!this.options?.pinOnDrag) { node.fx = null; node.fy = null }
        this.appearanceDirty = true
        if (!event.active) this.simulation.alphaTarget(0)
        this.draw()
      }))
  }

  private draw() {
    if (this.destroyed) return
    this.nodeElements?.attr('transform', node => `translate(${node.x || 0},${node.y || 0})`)
    this.edgeElements?.attr('d', forceEdgePath)
    if (this.appearanceDirty) {
      const selected = this.options?.selected, hovered = this.hovered
      const neighbors = new Set(selected ? [selected] : [])
      const highlighted = new Set(this.options?.highlighted || [])
      this.edges.forEach(edge => { if (edge.source.id === selected || edge.target.id === selected) { neighbors.add(edge.source.id); neighbors.add(edge.target.id) } })
      this.nodeElements?.attr('aria-pressed', node => String(node.id === selected)).classed('is-selected', node => node.id === selected)
        .classed('is-hovered', node => node.id === hovered).classed('is-evidence', node => highlighted.has(node.id))
        .classed('is-faded', node => !!selected && !neighbors.has(node.id) && node.id !== hovered && !highlighted.has(node.id))
      this.nodeElements?.select('circle.d3-pin').attr('display', node => node.fx == null ? 'none' : null)
      this.edgeElements?.classed('is-lifecycle', edge => edge.resource.properties.origin === 'lifecycle_assertion')
        .classed('is-context', edge => edge.source.id === selected || edge.target.id === selected || edge.id === this.hoveredEdge)
        .classed('is-faded', edge => !!selected && edge.source.id !== selected && edge.target.id !== selected && edge.id !== this.hoveredEdge)
        .attr('marker-end', edge => `url(#${this.markerPrefix}-${edge.source.id === selected || edge.target.id === selected || edge.id === this.hoveredEdge ? 'context' : edge.resource.properties.origin === 'lifecycle_assertion' ? 'lifecycle' : 'normal'})`)
      this.drawLabels()
      this.appearanceDirty = false
    }
    this.labelElements?.filter(function () { return this.getAttribute('display') !== 'none' }).attr('x', edge => forceEdgeLabelPoint(edge).x)
      .attr('y', edge => forceEdgeLabelPoint(edge).y)
  }

  private drawLabels() {
    const selected = this.options?.selected
    const highlighted = new Set(this.options?.highlighted || [])
    this.nodeElements?.select('text.d3-node-label').attr('display', node => this.options?.allLabels || node.id === selected || node.id === this.hovered || this.nodes.length <= 55
      || highlighted.has(node.id) || this.transform.k > 1 || node.resource.type === 'repository' ? null : 'none')
    this.labelElements?.attr('display', edge => edge.id === this.hoveredEdge || (this.transform.k > .6 && this.edges.length < 80
      && edge.resource.properties.origin === 'lifecycle_assertion' && (edge.source.id === selected || edge.target.id === selected)) ? null : 'none')
      .filter(function () { return this.getAttribute('display') !== 'none' })
      .attr('x', edge => forceEdgeLabelPoint(edge).x)
      .attr('y', edge => forceEdgeLabelPoint(edge).y)
  }

  fit = () => {
    if (!this.nodes.length || this.width <= 1 || this.height <= 1) return
    const xs = this.nodes.map(node => node.x || 0), ys = this.nodes.map(node => node.y || 0)
    const left = Math.min(...xs) - 65, right = Math.max(...xs) + 65, top = Math.min(...ys) - 50, bottom = Math.max(...ys) + 75
    const scale = Math.max(.025, Math.min(1.6, (this.width - 70) / Math.max(1, right - left), (this.height - 70) / Math.max(1, bottom - top)))
    this.svg.call(this.zoomBehavior.transform, zoomIdentity.translate(this.width / 2 - (left + right) / 2 * scale, this.height / 2 - (top + bottom) / 2 * scale).scale(scale))
    this.fitted = true
  }
  zoomBy = (factor: number) => { this.svg.call(this.zoomBehavior.scaleBy, factor) }
  reheat = () => { if (this.nodes.length && !this.options?.paused) this.simulation.alpha(.8).alphaTarget(0).restart() }
  releasePins = () => { this.cache.forEach(node => { node.fx = null; node.fy = null }); this.appearanceDirty = true; this.draw(); this.reheat() }
  destroy() {
    this.destroyed = true
    this.simulation.stop().on('tick.render', null)
    this.resizeObserver.disconnect()
    if (this.activeWindow) { select(this.activeWindow).on('mousemove.drag mouseup.drag', null); dragEnable(this.activeWindow) }
    this.svg.on('.zoom', null).on('.graph', null).remove()
    this.cache.clear(); this.nodes = []; this.edges = []
  }
}
