import { describe, expect, it } from 'vitest'
import type { TraceGraph } from './types'
import { DEPENDS_ON, dependencyAnalysis, dependencyIndex, lineagePreview, lineageSvg } from './supplyChainModel'

function fixture(): TraceGraph {
  return { nodes: ['app', 'a', 'b', 'c', 'isolated'].map(id => ({ id, label: id, type: id === 'app' ? 'repository' : 'sbom_component', properties: {} })),
    edges: [['app', 'a'], ['a', 'b'], ['b', 'c'], ['c', 'a']].map(([source, target]) => ({ source, target, type: DEPENDS_ON, properties: {} })).concat([
      { source: 'app', target: 'c', type: 'urn:codetrace:vocab:contains', properties: {} }]), metadata: {} }
}
describe('supply-chain lineage', () => {
  it('finds a directed shortest path without shortcuts through inventory membership', () => {
    const result = dependencyAnalysis(dependencyIndex(fixture()), 'path', 'app', 'c')
    expect(result.path).toEqual(['app', 'a', 'b', 'c'])
    expect(result.edges).toHaveLength(3)
  })
  it('reports descendants and ancestors without looping on cycles', () => {
    const index = dependencyIndex(fixture())
    expect(dependencyAnalysis(index, 'dependencies', 'a').ids).toEqual(['a', 'b', 'c'])
    expect(new Set(dependencyAnalysis(index, 'dependents', 'c').ids)).toEqual(new Set(['c', 'b', 'a', 'app']))
    expect(dependencyAnalysis(index, 'path', 'isolated', 'c').found).toBe(false)
    expect(dependencyAnalysis(index, 'path', 'a', 'a').path).toEqual(['a'])
    expect(dependencyAnalysis(index, 'dependencies', 'missing').ids).toEqual([])
  })
  it('deduplicates relationships and reports missing endpoints', () => {
    const graph = fixture()
    graph.edges.push(graph.edges[0], { source: 'app', target: 'missing', type: DEPENDS_ON, properties: {} })
    const index = dependencyIndex(graph)
    expect(index.edges).toHaveLength(4)
    expect(index.dangling).toBe(1)
    expect(dependencyAnalysis(index, 'inventory', '').ids).toHaveLength(5)
  })
  it('does not infer roots from inventory-only containment', () => {
    const graph = fixture(); graph.edges = graph.edges.filter(edge => edge.source !== 'app' || edge.type !== DEPENDS_ON)
    expect(dependencyAnalysis(dependencyIndex(graph), 'path', 'app', 'c').found).toBe(false)
  })
  it('traverses beyond six hops and keeps complete results despite canvas limits', () => {
    const graph: TraceGraph = { nodes: Array.from({ length: 250 }, (_, i) => ({ id: String(i), label: String(i), type: 'sbom_component', properties: {} })),
      edges: Array.from({ length: 249 }, (_, i) => ({ source: String(i), target: String(i + 1), type: DEPENDS_ON, properties: {} })), metadata: {} }
    const index = dependencyIndex(graph), result = dependencyAnalysis(index, 'path', '0', '249')
    expect(result.path).toHaveLength(250)
    expect(result.edges).toHaveLength(249)
    const preview = lineagePreview(index, result)
    expect(preview.nodes).toHaveLength(200)
    expect(preview.edges).toHaveLength(199)
    expect(preview.truncated).toBe(true)
  })
  it('escapes untrusted labels in standalone SVG and omits missing endpoints', () => {
    const graph = fixture(); graph.nodes[0].label = '<script>alert("x")</script>'
    const svg = lineageSvg(graph.nodes, graph.edges, 'A & B')
    expect(svg).toContain('&lt;script&gt;')
    expect(svg).not.toContain('<script>')
    expect(svg).toContain('A &amp; B')
    expect(svg).toContain('consumer to dependency')
  })
  it.each(['dependencies', 'dependents', 'inventory'] as const)('preserves connecting witnesses in a dense %s preview', mode => {
    const graph: TraceGraph = { nodes: ['app', ...Array.from({ length: 40 }, (_, i) => `p${i}`)].map(id => ({
      id, label: id, type: id === 'app' ? 'repository' : 'sbom_component', properties: {},
    })), edges: [], metadata: {} }
    for (let i = 0; i < 40; i++) for (let j = i + 1; j < 40; j++) {
      graph.edges.push({ source: `p${i}`, target: `p${j}`, type: DEPENDS_ON, properties: {} })
    }
    graph.edges.push({ source: 'app', target: 'p0', type: DEPENDS_ON, properties: {} })
    const unchanged = JSON.stringify(graph)
    const index = dependencyIndex(graph)
    const result = dependencyAnalysis(index, mode, mode === 'dependents' ? 'p39' : 'app')
    const preview = lineagePreview(index, result)
    expect(preview.nodes).toHaveLength(41)
    expect(preview.edges).toHaveLength(500)
    expect(preview.truncated).toBe(true)
    expect(preview.edges.some(edge => edge.source === 'app' && edge.target === 'p0')).toBe(true)
    const reduced = dependencyIndex({ ...graph, nodes: preview.nodes, edges: preview.edges })
    const walked = dependencyAnalysis(reduced, mode === 'dependents' ? 'dependents' : 'dependencies', mode === 'dependents' ? 'p39' : 'app')
    expect(new Set(walked.ids)).toEqual(new Set(result.ids))
    expect(JSON.stringify(graph)).toBe(unchanged)
  })
  it('renders SVG self-dependencies as a non-degenerate loop', () => {
    const node = { id: 'a', label: 'A', type: 'sbom_component', properties: {} }
    const svg = lineageSvg([node], [{ source: 'a', target: 'a', type: DEPENDS_ON, properties: {} }], 'Self loop')
    expect(svg).toContain('M510,60 C760,10 760,140 510,90')
    expect(svg).not.toContain('M510,75 C950,75 950,75 510,75')
    expect(svg).toContain('<g><title>a depends on a</title><path')
  })
})
