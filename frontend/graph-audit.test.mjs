// Node 22.13+ contract tests; runs without npm dependencies.
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const moduleUrl = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64')
const types = moduleUrl(stripTypeScriptTypes(readFileSync(new URL('./src/workspace/types.ts', import.meta.url), 'utf8')))
const source = stripTypeScriptTypes(readFileSync(new URL('./src/workspace/graphModel.ts', import.meta.url), 'utf8'))
const { visibleGraph, localContext, containmentDescendants } = await import(moduleUrl(source.replace("'./types'", JSON.stringify(types))))
const graph = { nodes: [
  { id: 'file', label: 'File', type: 'file', properties: { domain: 'CODE' } },
  { id: 'fn', label: 'Function', type: 'function', properties: { domain: 'CODE' } },
  { id: 'req', label: 'Requirement', type: 'requirement', properties: { domain: 'RM' } },
], edges: [
  { source: 'file', target: 'fn', type: 'contains', properties: {} },
  { source: 'req', target: 'fn', type: 'implementedBy', properties: { origin: 'lifecycle_assertion' } },
], metadata: {} }

test('overview keeps symbol lifecycle evidence and prioritizes it under edge limits', () => {
  const view = visibleGraph(graph, 'ALL', false, 10, 1)
  assert.ok(view.nodes.some(node => node.id === 'fn'))
  assert.equal(view.edges[0].type, 'implementedBy')
  assert.equal(view.omittedEdges, 1)
})
test('node limits never leave dangling edges or mutate input ordering', () => {
  const before = JSON.stringify(graph)
  const view = visibleGraph(graph, 'ALL', true, 2, 10)
  const ids = new Set(view.nodes.map(node => node.id))
  assert.ok(view.edges.every(edge => ids.has(edge.source) && ids.has(edge.target)))
  assert.equal(JSON.stringify(graph), before)
})
test('exact domain filtering and bounded focus preserve declared context', () => {
  assert.deepEqual(visibleGraph(graph, 'RM', false, 10, 10).nodes.map(node => node.id), ['req'])
  assert.deepEqual([...localContext(graph, 'req', 1)].sort(), ['fn', 'req'])
})
test('collapse hides descendants without following lifecycle links and expand restores them', () => {
  const descendants = containmentDescendants(graph, 'file')
  assert.deepEqual([...descendants], ['fn'])
  const collapsed = visibleGraph(graph, 'ALL', true, 10, 10, undefined, new Set(['file']))
  assert.ok(!collapsed.nodes.some(node => node.id === 'fn'))
  assert.ok(collapsed.nodes.some(node => node.id === 'req'))
  assert.equal(visibleGraph(graph, 'ALL', true, 10, 10).nodes.length, 3)
})
test('containment cycles terminate without hiding the collapsed root', () => {
  const cyclic = { ...graph, edges: [...graph.edges, { source: 'fn', target: 'file', type: 'contains', properties: {} }] }
  assert.deepEqual([...containmentDescendants(cyclic, 'file')], ['fn'])
})
test('selected context survives preview limits', () => {
  assert.equal(visibleGraph(graph, 'ALL', true, 1, 10, undefined, new Set(), 'file').nodes[0].id, 'file')
})
test('hierarchical traversal follows the requested direction and context', () => {
  assert.deepEqual([...localContext(graph, 'fn', 2, 'incoming', 'hierarchy')].sort(), ['file', 'fn'])
  assert.deepEqual([...localContext(graph, 'fn', 2, 'outgoing', 'hierarchy')], ['fn'])
  assert.deepEqual([...localContext(graph, 'fn', 1, 'incoming', 'evidence')].sort(), ['fn', 'req'])
  assert.deepEqual([...localContext(graph, 'req', 1, 'outgoing', 'evidence')].sort(), ['fn', 'req'])
})
test('unknown traversal roots and dangling edges do not introduce resources', () => {
  const broken = { ...graph, edges: [...graph.edges, { source: 'fn', target: 'missing', type: 'calls', properties: {} }] }
  assert.equal(localContext(broken, 'missing').size, 0)
  assert.ok(!localContext(broken, 'fn').has('missing'))
})
test('displayed relationships respect the traversal context without rewriting graph data', () => {
  const view = visibleGraph(graph, 'ALL', true, 10, 10, new Set(['file', 'fn', 'req']), new Set(), 'fn', 'evidence')
  assert.deepEqual(view.edges.map(edge => edge.type), ['implementedBy'])
  assert.equal(graph.edges.length, 2)
})
