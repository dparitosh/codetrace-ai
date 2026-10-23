import type { TraceEdge, TraceGraph, TraceNode } from './types'

export const DEPENDS_ON = 'urn:codetrace:vocab:depends_on'
export type SupplyMode = 'path' | 'dependencies' | 'dependents' | 'inventory'
export function dependencyIndex(graph: TraceGraph) {
  const nodes = new Map(graph.nodes.filter(node => ['repository', 'sbom_component'].includes(node.type)).map(node => [node.id, node]))
  const outgoing = new Map<string, string[]>(), incoming = new Map<string, string[]>()
  const seen = new Set<string>(), edges: TraceEdge[] = []
  let dangling = 0
  for (const edge of graph.edges) {
    if (edge.type !== DEPENDS_ON) continue
    if (!nodes.has(edge.source) || !nodes.has(edge.target)) { dangling++; continue }
    const key = JSON.stringify([edge.source, edge.target])
    if (seen.has(key)) continue
    seen.add(key); edges.push(edge)
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, [])
    if (!incoming.has(edge.target)) incoming.set(edge.target, [])
    outgoing.get(edge.source)!.push(edge.target)
    incoming.get(edge.target)!.push(edge.source)
  }
  return { nodes, edges, outgoing, incoming, dangling }
}
export type DependencyIndex = ReturnType<typeof dependencyIndex>

/** Breadth-first traversal of the complete snapshot, independent of canvas limits. */
export function dependencyAnalysis(index: DependencyIndex, mode: SupplyMode, start: string, target = '') {
  const parent = new Map<string, string>(), depth = new Map<string, number>()
  const order: string[] = []
  if (mode === 'inventory') order.push(...index.nodes.keys())
  else if (index.nodes.has(start)) {
    order.push(start); depth.set(start, 0)
    const adjacency = mode === 'dependents' ? index.incoming : index.outgoing
    for (let cursor = 0; cursor < order.length; cursor++) {
      const current = order[cursor]
      for (const next of adjacency.get(current) || []) {
        if (depth.has(next)) continue
        parent.set(next, current); depth.set(next, depth.get(current)! + 1); order.push(next)
      }
    }
  }
  const path: string[] = []
  if (depth.has(target)) {
    let current = target
    path.push(current)
    while (parent.has(current)) { current = parent.get(current)!; path.push(current) }
    path.reverse()
  }
  const ids = mode === 'path' ? path : order
  const selected = new Set(ids)
  const pairs = new Set(path.slice(1).map((id, i) => JSON.stringify([path[i], id])))
  const edges = index.edges.filter(edge => selected.has(edge.source) && selected.has(edge.target)
    && (mode !== 'path' || pairs.has(JSON.stringify([edge.source, edge.target]))))
  const backbone = edges.filter(edge => mode === 'dependents'
    ? parent.get(edge.source) === edge.target : parent.get(edge.target) === edge.source)
  return { ids, edges, backbone, depth, path, reachable: order.length, found: path.length > 0 }
}

export function lineagePreview(index: DependencyIndex, analysis: ReturnType<typeof dependencyAnalysis>, limit = 200) {
  const nodes = analysis.ids.slice(0, Math.max(0, Math.min(200, limit))).map(id => index.nodes.get(id)!)
  const ids = new Set(nodes.map(node => node.id))
  const edges = analysis.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target))
  // Preserve directed traversal witnesses first. For inventory views, retain a
  // spanning forest before spending the edge budget on dense local clusters.
  const chosen = new Set(analysis.backbone.filter(edge => ids.has(edge.source) && ids.has(edge.target)))
  const representatives = new Map(nodes.map(node => [node.id, node.id]))
  const find = (id: string): string => {
    let root = id
    while (representatives.get(root) !== root) root = representatives.get(root)!
    while (id !== root) { const next = representatives.get(id)!; representatives.set(id, root); id = next }
    return root
  }
  const connect = (edge: TraceEdge) => {
    const a = find(edge.source), b = find(edge.target)
    if (a === b) return false
    representatives.set(a, b); return true
  }
  chosen.forEach(connect)
  edges.forEach(edge => { if (connect(edge)) chosen.add(edge) })
  for (const edge of edges) { if (chosen.size >= 500) break; chosen.add(edge) }
  return { nodes, edges: [...chosen], truncated: nodes.length < analysis.ids.length || edges.length > 500 }
}

const xml = (text: string) => text.replace(/[&<>"']/g, value => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[value]!)
export function lineageSvg(nodes: TraceNode[], edges: TraceEdge[], title: string) {
  // A deterministic, readable dependency diagram. Export exactly the bounded preview.
  const width = 1000, height = Math.max(160, nodes.length * 85 + 80)
  const positions = new Map(nodes.map((node, i) => [node.id, { x: 270, y: i * 85 + 75 }]))
  const links = edges.map(edge => {
    const a = positions.get(edge.source), b = positions.get(edge.target)
    if (!a || !b) return ''
    const path = edge.source === edge.target
      ? `M510,${a.y - 15} C760,${a.y - 65} 760,${a.y + 65} 510,${a.y + 15}`
      : `M510,${a.y} C950,${a.y} 950,${b.y} 510,${b.y}`
    return `<g><title>${xml(edge.source)} depends on ${xml(edge.target)}</title><path d="${path}" fill="none" stroke="#526b86" marker-end="url(#arrow)"/></g>`
  }).join('')
  const boxes = nodes.map(node => {
    const p = positions.get(node.id)!
    return `<g><title>${xml(node.label)} (${xml(node.id)})</title><rect x="30" y="${p.y - 25}" width="480" height="50" rx="8" fill="${node.type === 'repository' ? '#dce8f4' : '#e2f0eb'}" stroke="#526b86"/><text x="45" y="${p.y + 5}" font-family="sans-serif" font-size="14">${xml(node.label.slice(0, 58))}</text></g>`
  }).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img"><title>${xml(title)}</title><desc>Dependency arrows point from consumer to dependency. Inventory membership is excluded. Bounded preview; see JSON for complete results.</desc><rect width="100%" height="100%" fill="white"/><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#526b86"/></marker></defs><text x="30" y="25" font-family="sans-serif" font-size="16">${xml(title)}</text>${links}${boxes}</svg>`
}
