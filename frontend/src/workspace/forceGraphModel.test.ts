import { describe, expect, it } from 'vitest'
import { forceLink, forceSimulation, forceX, forceY } from 'd3-force'
import { forceEdgePath, hierarchyLevels, layoutTargets, reconcileForceEdges, reconcileForceNodes, rebindForceNodes, type ForceNode, type ForceEdge, type ForceLayout } from './forceGraphModel'
import type { TraceEdge, TraceNode } from './types'

const resources: TraceNode[] = ['file', 'function', 'rm'].map(id => ({ id, label: id, type: id === 'file' ? 'file' : 'resource', properties: {} }))
const relation = (source: string, target: string, type = 'contains'): TraceEdge => ({ source, target, type, properties: {} })

describe('D3 simulation boundaries', () => {
  it('drops obsolete force targets before restoring collapsed nodes', () => {
    const nodes = reconcileForceNodes(new Map(), resources, [])
    const targets = new Map([[nodes[0].id, { x: 0, y: 0 }]])
    const simulation = forceSimulation<ForceNode>([nodes[0]]).stop()
      .force('x', forceX<ForceNode>(node => targets.get(node.id)!.x))
      .force('y', forceY<ForceNode>(node => targets.get(node.id)!.y))
    expect(() => rebindForceNodes(simulation, nodes)).not.toThrow()
    expect(simulation.nodes()).toHaveLength(3)
    expect(simulation.force('x')).toBeUndefined()
    simulation.tick(5)
    expect(nodes.every(node => Number.isFinite(node.x))).toBe(true)
  })
  it('preserves hidden positions and pins without mutating snapshot data', () => {
    const original = structuredClone(resources)
    const cache = new Map<string, ForceNode>()
    const nodes = reconcileForceNodes(cache, resources, [])
    nodes[1].x = 123; nodes[1].y = 456; nodes[1].fx = 123; nodes[1].fy = 456
    reconcileForceNodes(cache, [resources[0]], [])
    const restored = reconcileForceNodes(cache, resources, [])
    expect(restored[1]).toBe(nodes[1])
    expect(restored[1]).toMatchObject({ x: 123, y: 456, fx: 123, fy: 456 })
    const raw = [relation('file', 'function'), relation('function', 'rm'), relation('rm', 'rm')]
    const before = structuredClone(raw)
    const links = reconcileForceEdges(restored, raw)
    const simulation = forceSimulation<ForceNode>(restored).stop().force('links', forceLink<ForceNode, ForceEdge>(links))
    simulation.tick(100)
    expect(restored.every(node => Number.isFinite(node.x) && Number.isFinite(node.y))).toBe(true)
    expect(resources).toEqual(original)
    expect(raw).toEqual(before)
    expect(raw[0].source).toBe('file')
  })

  it('filters dangling endpoints and separates parallel, reverse and self-links', () => {
    const nodes = reconcileForceNodes(new Map(), resources, [])
    nodes[0].x = 0; nodes[0].y = 0; nodes[1].x = 200; nodes[1].y = 0
    const edges = reconcileForceEdges(nodes, [relation('file', 'function'), relation('function', 'file'),
      relation('file', 'function'), relation('rm', 'rm'), relation('rm', 'rm'), relation('absent', 'file')])
    expect(edges).toHaveLength(5)
    expect(new Set(edges.map(edge => edge.id)).size).toBe(5)
    expect(new Set(edges.map(forceEdgePath)).size).toBe(5)
    expect(edges.map(forceEdgePath).join('')).not.toMatch(/NaN|Infinity/)
  })

  it('layers mixed containment and lifecycle evidence from the focused resource', () => {
    const nodes = reconcileForceNodes(new Map(), resources, [])
    const edges = reconcileForceEdges(nodes, [relation('file', 'function'), relation('rm', 'function', 'implementedBy')])
    expect(hierarchyLevels(nodes, edges, 'rm', 'outgoing').get('function')).toBe(1)
    expect(hierarchyLevels(nodes, edges, 'function', 'incoming').get('rm')).toBe(-1)
    expect(hierarchyLevels(nodes, edges, 'function', 'incoming').get('file')).toBe(-1)
  })

  it('produces finite targets for cycles, disconnected nodes and empty views in every layout', () => {
    const nodes = reconcileForceNodes(new Map(), resources, [])
    const edges = reconcileForceEdges(nodes, [relation('file', 'function'), relation('function', 'file')])
    for (const layout of ['hierarchy', 'force', 'circle', 'concentric', 'grid'] as ForceLayout[]) {
      const targets = layoutTargets(nodes, edges, layout, null, 'both')
      expect(targets.size).toBe(3)
      expect([...targets.values()].every(point => Number.isFinite(point.x) && Number.isFinite(point.y))).toBe(true)
      expect(layoutTargets([], [], layout, null, 'both').size).toBe(0)
    }
  })
})
