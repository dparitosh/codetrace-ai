import { domainOf } from './types'
import type { TraceGraph, TraceNode } from './types'

export function containmentDescendants(graph: TraceGraph, root: string) {
  const known = new Set(graph.nodes.map(node => node.id))
  if (!known.has(root)) return new Set<string>()
  const children = new Map<string, string[]>()
  graph.edges.forEach(edge => {
    if (!known.has(edge.source) || !known.has(edge.target)) return
    if (isContainment(edge.type)) {
      if (!children.has(edge.source)) children.set(edge.source, [])
      children.get(edge.source)!.push(edge.target)
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

export function revealContextRoot(graph: TraceGraph, collapsedIds: Set<string>, nodeId: string) {
  return new Set([...collapsedIds].filter(root => !containmentDescendants(graph, root).has(nodeId)))
}

export function visibleGraph(graph: TraceGraph, domain: string, detail: boolean, limit: number, edgeLimit: number, focusIds?: Set<string>, collapsedIds = new Set<string>(), selectedId?: string | null, relationScope: RelationScope = 'all') {
  const lifecycleEndpoints = new Set<string>()
  graph.edges.forEach(edge => {
    if (edge.properties.origin === 'lifecycle_assertion') {
      lifecycleEndpoints.add(edge.source); lifecycleEndpoints.add(edge.target)
    }
  })
  let candidates = graph.nodes.filter(node => (domain === 'ALL' || domainOf(node) === domain)
    && (detail || node.id === selectedId || lifecycleEndpoints.has(node.id) || !['variable', 'external_symbol', 'function', 'method', 'symbol'].includes(node.type)))
  if (focusIds) candidates = graph.nodes.filter(node => focusIds.has(node.id) && (domain === 'ALL' || domainOf(node) === domain))
  const hidden = new Set<string>()
  collapsedIds.forEach(root => containmentDescendants(graph, root).forEach(id => hidden.add(id)))
  candidates = candidates.filter(node => !hidden.has(node.id))
  const degree = new Map<string, number>()
  const contextOrder = focusIds ? new Map([...focusIds].map((id, index) => [id, index])) : null
  graph.edges.forEach(edge => { degree.set(edge.source, (degree.get(edge.source) || 0) + 1); degree.set(edge.target, (degree.get(edge.target) || 0) + 1) })
  candidates.sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId)
    || (contextOrder ? contextOrder.get(a.id)! - contextOrder.get(b.id)! : 0)
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

export function matchingNodes(graph: TraceGraph | null, query: string, limit = 12): TraceNode[] {
  if (!graph || !query.trim()) return []
  const value = query.toLowerCase().trim()
  return graph.nodes.map(node => {
    const label = node.label.toLowerCase()
    const identity = `${node.id} ${node.properties.identifier || ''} ${node.properties.code_id || ''} ${node.properties.uri || ''}`.toLowerCase()
    const score = node.id.toLowerCase() === value ? 2000 : label === value ? 1000 : label.startsWith(value) ? 500 : label.includes(value) ? 100
      : identity.includes(value) ? 60
      : `${node.type} ${domainOf(node)} ${node.properties.path || ''} ${node.properties.description || ''}`.toLowerCase().includes(value) ? 10 : 0
    return { node, score }
  }).filter(item => item.score > 0).sort((a, b) => b.score - a.score || a.node.id.localeCompare(b.node.id))
    .slice(0, limit).map(item => item.node)
}

export type TraversalDirection = 'both' | 'outgoing' | 'incoming'
export type RelationScope = 'all' | 'hierarchy' | 'evidence'

function isContainment(type: string) {
  return ['contains', 'defines', 'urn:codetrace:vocab:contains', 'urn:codetrace:vocab:defines'].includes(type)
}

export function matchesRelationScope(type: string, scope: RelationScope) {
  const hierarchy = isContainment(type)
  const metadata = ['instanceShape', 'serviceProvider', 'http://open-services.net/ns/core#instanceShape', 'http://open-services.net/ns/core#serviceProvider'].includes(type)
  return scope === 'all' || (scope === 'hierarchy' ? hierarchy : !hierarchy && !metadata)
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
