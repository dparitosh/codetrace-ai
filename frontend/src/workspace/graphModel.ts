import { domainOf } from './types'
import type { TraceGraph, TraceNode } from './types'

export function containmentDescendants(graph: TraceGraph, root: string) {
  const children = new Map<string, string[]>()
  graph.edges.forEach(edge => {
    if (['contains', 'defines'].includes(edge.type.split('#').pop()?.split(':').pop() || '')) {
      children.set(edge.source, [...(children.get(edge.source) || []), edge.target])
    }
  })
  const visited = new Set([root]); const queue = [root]
  for (let index = 0; index < queue.length; index++) {
    for (const child of children.get(queue[index]) || []) {
      if (!visited.has(child)) { visited.add(child); queue.push(child) }
    }
  }
  visited.delete(root)
  return visited
}

export function visibleGraph(graph: TraceGraph, domain: string, detail: boolean, limit: number, edgeLimit: number, focusIds?: Set<string>, collapsedIds = new Set<string>(), selectedId?: string | null, relationScope: RelationScope = 'all') {
  const lifecycleEndpoints = new Set<string>()
  graph.edges.forEach(edge => {
    if (edge.properties.origin === 'lifecycle_assertion') {
      lifecycleEndpoints.add(edge.source); lifecycleEndpoints.add(edge.target)
    }
  })
  let candidates = graph.nodes.filter(node => (domain === 'ALL' || domainOf(node) === domain)
    && (detail || lifecycleEndpoints.has(node.id) || !['variable', 'external_symbol', 'function', 'method', 'symbol'].includes(node.type)))
  if (focusIds) candidates = graph.nodes.filter(node => focusIds.has(node.id))
  const hidden = new Set<string>()
  collapsedIds.forEach(root => containmentDescendants(graph, root).forEach(id => hidden.add(id)))
  candidates = candidates.filter(node => !hidden.has(node.id))
  const degree = new Map<string, number>()
  graph.edges.forEach(edge => { degree.set(edge.source, (degree.get(edge.source) || 0) + 1); degree.set(edge.target, (degree.get(edge.target) || 0) + 1) })
  candidates.sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId)
    || Number(lifecycleEndpoints.has(b.id)) - Number(lifecycleEndpoints.has(a.id))
    || Number(domainOf(b) !== 'CODE') - Number(domainOf(a) !== 'CODE')
    || (degree.get(b.id) || 0) - (degree.get(a.id) || 0) || a.id.localeCompare(b.id))
  const nodes = candidates.slice(0, limit)
  const visible = new Set(nodes.map(node => node.id))
  const eligibleEdges = graph.edges.filter(edge => visible.has(edge.source) && visible.has(edge.target) && matchesRelationScope(edge.type, relationScope))
    .sort((a, b) => Number(b.properties.origin === 'lifecycle_assertion') - Number(a.properties.origin === 'lifecycle_assertion'))
  const edges = eligibleEdges.slice(0, edgeLimit)
  return { nodes, edges, omittedEdges: eligibleEdges.length - edges.length, omitted: candidates.length - nodes.length, total: candidates.length }
}

export function matchingNodes(graph: TraceGraph | null, query: string): TraceNode[] {
  if (!graph || !query.trim()) return []
  const value = query.toLowerCase().trim()
  return graph.nodes.map(node => {
    const label = node.label.toLowerCase()
    const score = label === value ? 1000 : label.startsWith(value) ? 500 : label.includes(value) ? 100
      : String(node.properties.identifier || '').toLowerCase().includes(value) ? 60
      : `${node.type} ${node.properties.path || ''}`.toLowerCase().includes(value) ? 10 : 0
    return { node, score }
  }).filter(item => item.score > 0).sort((a, b) => b.score - a.score || a.node.id.localeCompare(b.node.id))
    .slice(0, 12).map(item => item.node)
}

export type TraversalDirection = 'both' | 'outgoing' | 'incoming'
export type RelationScope = 'all' | 'hierarchy' | 'evidence'

export function matchesRelationScope(type: string, scope: RelationScope) {
  const relation = type.split('#').pop()?.split(':').pop()
  const hierarchy = relation === 'contains' || relation === 'defines'
  return scope === 'all' || (scope === 'hierarchy' ? hierarchy : !hierarchy && relation !== 'instanceShape' && relation !== 'serviceProvider')
}

export function localContext(graph: TraceGraph, nodeId: string, depth = 1,
  direction: TraversalDirection = 'both', scope: RelationScope = 'all') {
  const known = new Set(graph.nodes.map(node => node.id))
  if (!known.has(nodeId)) return new Set<string>()
  const adjacency = new Map<string, Set<string>>()
  const connect = (source: string, target: string) => {
    if (!adjacency.has(source)) adjacency.set(source, new Set())
    adjacency.get(source)!.add(target)
  }
  graph.edges.forEach(edge => {
    if (!known.has(edge.source) || !known.has(edge.target)) return
    if (!matchesRelationScope(edge.type, scope)) return
    if (direction !== 'incoming') connect(edge.source, edge.target)
    if (direction !== 'outgoing') connect(edge.target, edge.source)
  })
  const ids = new Set([nodeId])
  let boundary = new Set(ids)
  for (let iteration = 0; iteration < Math.min(6, Math.max(0, depth)); iteration++) {
    const next = new Set<string>()
    boundary.forEach(source => {
      adjacency.get(source)?.forEach(target => { if (!ids.has(target)) { ids.add(target); next.add(target) } })
    })
    if (!next.size) break
    boundary = next
  }
  return ids
}
