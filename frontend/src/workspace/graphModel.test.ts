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
  it('focuses connected context and omits unrelated files', () => {
    const ids = localContext(graph, 'rm', 2)
    expect(ids.has('function')).toBe(true)
    expect(ids.has('file')).toBe(true)
    expect(ids.has('other')).toBe(false)
  })
})
