import { describe, expect, it } from 'vitest'
import { localContext, matchingNodes, visibleGraph } from './graphModel'
import { TraceGraph } from './types'

const graph: TraceGraph = { nodes: [
  { id: 'file', label: 'service.py', type: 'file', properties: { domain: 'CODE', path: 'src/service.py' } },
  { id: 'function', label: 'charge', type: 'function', properties: { domain: 'CODE' } },
  { id: 'rm', label: 'Charge customer', type: 'requirement', properties: { domain: 'RM' } },
  { id: 'other', label: 'Other module', type: 'file', properties: { domain: 'CODE' } },
], edges: [
  { source: 'file', target: 'function', type: 'contains', properties: {} },
  { source: 'rm', target: 'function', type: 'implementedBy', properties: { origin: 'lifecycle_assertion' } },
], metadata: {} }

describe('interactive graph projection', () => {
  it('connects a bounded preview through low-degree bridge nodes and includes deep symbols', () => {
    const nodes = ['repo', 'pkg', 'file', 'class', 'method', 'variable', 'feature'].map((id, index) => ({
      id, label: id, type: ['repository', 'package', 'file', 'class', 'method', 'variable', 'feature'][index], properties: {},
    }))
    const edges = nodes.slice(1).map((node, index) => ({ source: nodes[index].id, target: node.id, type: 'contains', properties: {} }))
    const snapshot = { nodes, edges, metadata: {} }
    const view = visibleGraph(snapshot, 'ALL', true, 6, 10)
    expect(view.nodes.map(node => node.id)).toEqual(['repo', 'pkg', 'file', 'class', 'method', 'variable'])
    expect(view.components).toBe(1)
    expect(view.edges).toHaveLength(5)
    const focused = visibleGraph(snapshot, 'ALL', true, 7, 10, localContext(snapshot, 'method', 2), new Set(), 'method')
    expect(focused.nodes.some(node => node.type === 'feature')).toBe(true)
    expect(focused.components).toBe(1)
  })
  it('spends edge limits on connectivity before parallel edges and reports real isolates', () => {
    const snapshot = { ...graph, edges: [graph.edges[0], { ...graph.edges[0], type: 'defines' }, graph.edges[1]] }
    const view = visibleGraph(snapshot, 'ALL', true, 100, 2)
    expect(view.edges.some(edge => edge.type === 'contains')).toBe(true)
    expect(view.edges.some(edge => edge.type === 'implementedBy')).toBe(true)
    expect(view.components).toBe(2) // The unrelated file is genuinely isolated.
    expect(view.omittedEdges).toBe(1)
  })
  it('uses only the selected relationship scope to grow a connected preview', () => {
    const view = visibleGraph(graph, 'ALL', true, 3, 10, undefined, new Set(), 'file', 'hierarchy')
    expect(view.nodes.slice(0, 2).map(node => node.id)).toEqual(['file', 'function'])
    expect(view.edges.every(edge => edge.type === 'contains')).toBe(true)
    expect(visibleGraph(graph, 'ALL', true, 100, 0).components).toBe(4)
  })
  it('keeps overview concise while symbol view preserves code/lifecycle links', () => {
    const overview = visibleGraph(graph, 'ALL', false, 100, 100)
    expect(overview.nodes.some(node => node.id === 'function')).toBe(true)
    expect(overview.edges.some(edge => edge.type === 'implementedBy')).toBe(true)
    const detail = visibleGraph(graph, 'ALL', true, 100, 100)
    expect(detail.edges).toHaveLength(2)
    expect(detail.nodes[0].id).toBe('rm')
  })
  it('prioritizes lifecycle edges and reports relationship truncation', () => {
    const view = visibleGraph(graph, 'ALL', true, 100, 1)
    expect(view.edges[0].type).toBe('implementedBy')
    expect(view.omittedEdges).toBe(1)
  })
  it('bounds previews and never creates edges with hidden endpoints', () => {
    const view = visibleGraph(graph, 'ALL', true, 2, 1)
    expect(view.omitted).toBe(2)
    const ids = new Set(view.nodes.map(node => node.id))
    expect(view.edges.every(edge => ids.has(edge.source) && ids.has(edge.target))).toBe(true)
  })
  it('searches labels and source locations without global scope changes', () => {
    expect(matchingNodes(graph, 'src/service')).toHaveLength(1)
    expect(matchingNodes(graph, 'Charge')).toHaveLength(2)
  })
  it('ranks exact resource labels above matching source paths before limiting results', () => {
    const noisy = { ...graph, nodes: [
      ...Array.from({ length: 15 }, (_, index) => ({ id: 'noise-' + index, label: 'symbol-' + index, type: 'variable', properties: { path: 'backend/source.py' } })),
      { id: 'package', label: 'backend', type: 'package', properties: { path: 'backend' } },
    ] }
    expect(matchingNodes(noisy, 'backend')[0].id).toBe('package')
  })
  it('focuses connected context and omits unrelated files', () => {
    const ids = localContext(graph, 'rm', 2)
    expect(ids.has('function')).toBe(true)
    expect(ids.has('file')).toBe(true)
    expect(ids.has('other')).toBe(false)
  })
})
