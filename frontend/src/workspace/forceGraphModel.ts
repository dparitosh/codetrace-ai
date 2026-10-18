import type { Simulation, SimulationLinkDatum, SimulationNodeDatum } from 'd3-force'
import type { TraceEdge, TraceNode } from './types'
import { matchesRelationScope } from './graphModel'

export type ForceLayout = 'hierarchy' | 'force' | 'circle' | 'concentric' | 'grid'
export interface ForceNode extends SimulationNodeDatum { id: string; resource: TraceNode; radius: number }
export interface ForceEdge extends SimulationLinkDatum<ForceNode> { id: string; source: ForceNode; target: ForceNode; resource: TraceEdge; lane: number }
export interface Point { x: number; y: number }

// Position forces close over the previous projection's targets. Remove them,
// along with links to hidden endpoints, before D3 initializes a new node array.
export function rebindForceNodes(simulation: Simulation<ForceNode, ForceEdge>, nodes: ForceNode[]) {
  return simulation.force('links', null).force('x', null).force('y', null).nodes(nodes)
}

// D3 may mutate simulation records, never the reviewed snapshot or its edges.
export function reconcileForceNodes(cache: Map<string, ForceNode>, nodes: TraceNode[], edges: TraceEdge[]) {
  const neighbors = new Map<string, string[]>()
  for (const edge of edges) {
    if (!neighbors.has(edge.source)) neighbors.set(edge.source, [])
    if (!neighbors.has(edge.target)) neighbors.set(edge.target, [])
    neighbors.get(edge.source)!.push(edge.target)
    neighbors.get(edge.target)!.push(edge.source)
  }
  return nodes.map((resource, index) => {
    const existing = cache.get(resource.id)
    if (existing) { existing.resource = resource; return existing }
    const anchor = neighbors.get(resource.id)?.map(id => cache.get(id)).find(node => node && Number.isFinite(node.x) && Number.isFinite(node.y))
    const angle = index * Math.PI * (3 - Math.sqrt(5))
    const distance = anchor ? 40 : 12 * Math.sqrt(index + 1)
    const node: ForceNode = { id: resource.id, resource, radius: resource.type === 'repository' ? 26 : resource.type === 'package' ? 22 : 16,
      x: (anchor?.x || 0) + Math.cos(angle) * distance, y: (anchor?.y || 0) + Math.sin(angle) * distance, vx: 0, vy: 0 }
    cache.set(node.id, node)
    return node
  })
}

export function reconcileForceEdges(nodes: ForceNode[], edges: TraceEdge[]): ForceEdge[] {
  const byId = new Map(nodes.map(node => [node.id, node]))
  const duplicates = new Map<string, number>()
  const groups = new Map<string, ForceEdge[]>()
  const links: ForceEdge[] = []
  for (const edge of edges) {
    const source = byId.get(edge.source), target = byId.get(edge.target)
    if (!source || !target) continue
    const base = JSON.stringify([edge.source, edge.target, edge.type, edge.properties.origin, edge.properties.asserted_by])
    const ordinal = duplicates.get(base) || 0
    duplicates.set(base, ordinal + 1)
    const link: ForceEdge = { id: base + ':' + ordinal, source, target, resource: edge, lane: 0 }
    links.push(link)
    const pair = JSON.stringify([edge.source, edge.target].sort())
    if (!groups.has(pair)) groups.set(pair, [])
    groups.get(pair)!.push(link)
  }
  for (const group of groups.values()) {
    group.forEach((edge, index) => { edge.lane = edge.source === edge.target ? index + 1 : (index - (group.length - 1) / 2) * (edge.source.id <= edge.target.id ? 1 : -1) })
  }
  return links
}

export function hierarchyLevels(nodes: ForceNode[], edges: ForceEdge[], focus: string | null, direction: 'both' | 'outgoing' | 'incoming') {
  const incoming = new Map<string, string[]>(), outgoing = new Map<string, string[]>()
  const connect = (map: Map<string, string[]>, source: string, target: string) => {
    if (!map.has(source)) map.set(source, [])
    map.get(source)!.push(target)
  }
  // Prefer containment, but retain directed evidence in mixed contexts.
  const containment = edges.filter(edge => matchesRelationScope(edge.resource.type, 'hierarchy'))
  for (const edge of [...containment, ...edges.filter(edge => !matchesRelationScope(edge.resource.type, 'hierarchy'))]) {
    connect(outgoing, edge.source.id, edge.target.id)
    connect(incoming, edge.target.id, edge.source.id)
  }
  const levels = new Map<string, number>()
  const known = new Set(nodes.map(node => node.id))
  const seeds = focus && known.has(focus) ? [focus] : nodes.filter(node => !incoming.has(node.id)).map(node => node.id)
  const visit = (seed: string) => {
    if (levels.has(seed)) return
    levels.set(seed, 0)
    const queue = [seed]
    for (let index = 0; index < queue.length; index++) {
      const id = queue[index], level = levels.get(id)!
      const steps: [string, number][] = []
      if (!focus || direction !== 'incoming') steps.push(...(outgoing.get(id) || []).map(target => [target, 1] as [string, number]))
      if (focus && direction !== 'outgoing') steps.push(...(incoming.get(id) || []).map(target => [target, -1] as [string, number]))
      for (const [target, delta] of steps) {
        if (!levels.has(target)) { levels.set(target, level + delta); queue.push(target) }
      }
    }
  }
  seeds.forEach(visit)
  nodes.forEach(node => visit(node.id)) // Disconnected components and cycles terminate.
  return levels
}

export function layoutTargets(nodes: ForceNode[], edges: ForceEdge[], layout: ForceLayout, focus: string | null, direction: 'both' | 'outgoing' | 'incoming'): Map<string, Point> {
  const result = new Map<string, Point>()
  if (layout === 'hierarchy') {
    const levels = hierarchyLevels(nodes, edges, focus, direction)
    const rows = new Map<number, ForceNode[]>()
    nodes.forEach(node => { const level = levels.get(node.id) || 0; if (!rows.has(level)) rows.set(level, []); rows.get(level)!.push(node) })
    let y = 0
    for (const [, row] of [...rows].sort(([a], [b]) => a - b)) {
      const columns = Math.min(12, row.length)
      row.forEach((node, index) => result.set(node.id, { x: (index % columns - (columns - 1) / 2) * 125, y: y + Math.floor(index / columns) * 115 }))
      y += Math.ceil(row.length / columns) * 115 + 90
    }
    const center = (y - 90) / 2
    result.forEach(point => { point.y -= center })
    return result
  }
  const columns = Math.max(1, Math.ceil(Math.sqrt(nodes.length)))
  nodes.forEach((node, index) => {
    const ring = layout === 'concentric' ? Math.floor(Math.sqrt(index)) : 0
    const first = ring * ring
    const count = layout === 'concentric' ? Math.min(nodes.length - first, 2 * ring + 1) : nodes.length
    const angle = ((layout === 'concentric' ? index - first : index) / Math.max(1, count)) * 2 * Math.PI - Math.PI / 2
    const radius = layout === 'concentric' ? ring * 115 : Math.max(100, nodes.length * 20)
    result.set(node.id, layout === 'grid' ? { x: (index % columns - (columns - 1) / 2) * 120, y: (Math.floor(index / columns) - (Math.ceil(nodes.length / columns) - 1) / 2) * 115 }
      : layout === 'force' ? { x: 0, y: 0 } : { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius })
  })
  return result
}

export function forceEdgePath(edge: ForceEdge) {
  const x1 = edge.source.x || 0, y1 = edge.source.y || 0, x2 = edge.target.x || 0, y2 = edge.target.y || 0
  if (edge.source.id === edge.target.id) {
    const radius = edge.source.radius, loop = radius + 30 + Math.abs(edge.lane) * 18
    return `M${x1 - radius * .7},${y1 - radius * .7}C${x1 - loop * 2},${y1 - loop * 2} ${x1 + loop * 2},${y1 - loop * 2} ${x1 + radius * .7},${y1 - radius * .7}`
  }
  const dx = x2 - x1, dy = y2 - y1, length = Math.max(.001, Math.hypot(dx, dy))
  const ux = dx / length, uy = dy / length
  const start = Math.min(edge.source.radius + 2, length / 3), end = Math.min(edge.target.radius + 8, length / 3)
  const cx = (x1 + x2) / 2 - uy * edge.lane * 42, cy = (y1 + y2) / 2 + ux * edge.lane * 42
  return `M${x1 + ux * start},${y1 + uy * start}Q${cx},${cy} ${x2 - ux * end},${y2 - uy * end}`
}

export function forceEdgeLabelPoint(edge: ForceEdge): Point {
  const x1 = edge.source.x || 0, y1 = edge.source.y || 0, x2 = edge.target.x || 0, y2 = edge.target.y || 0
  if (edge.source === edge.target) {
    const radius = edge.source.radius, loop = radius + 30 + Math.abs(edge.lane) * 18
    return { x: x1, y: y1 - radius * .175 - loop * 1.5 - 6 }
  }
  const dx = x2 - x1, dy = y2 - y1, length = Math.max(.001, Math.hypot(dx, dy))
  const ux = dx / length, uy = dy / length
  const start = Math.min(edge.source.radius + 2, length / 3), end = Math.min(edge.target.radius + 8, length / 3)
  return { x: (x1 + x2) / 2 + ux * (start - end) / 4 - uy * edge.lane * 21,
    y: (y1 + y2) / 2 + uy * (start - end) / 4 + ux * edge.lane * 21 - 6 }
}
