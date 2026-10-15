// Reproducible model benchmark; no application or npm dependencies required.
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import assert from 'node:assert/strict'
import { performance } from 'node:perf_hooks'
const moduleUrl = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64')
const types = moduleUrl(stripTypeScriptTypes(readFileSync(new URL('./src/workspace/types.ts', import.meta.url), 'utf8')))
const source = stripTypeScriptTypes(readFileSync(new URL('./src/workspace/graphModel.ts', import.meta.url), 'utf8'))
const { visibleGraph, localContext, matchingNodes } = await import(moduleUrl(source.replace("'./types'", JSON.stringify(types))))
const graph = { nodes: [], edges: [], metadata: {} }
for (let index = 0; index < 50000; index++) {
  graph.nodes.push({ id: `node-${index}`, label: `Resource ${index}`, type: 'file', properties: { domain: 'CODE' } })
  if (index) graph.edges.push({ source: 'node-0', target: `node-${index}`, type: 'contains', properties: {} })
  if (index > 1) graph.edges.push({ source: `node-${index - 1}`, target: `node-${index}`, type: 'calls', properties: {} })
}
function measure(name, operation) {
  const start = performance.now()
  const value = operation()
  console.log(`${name}: ${(performance.now() - start).toFixed(1)} ms`)
  return value
}
const view = measure('50k nodes / 99,997 edges: overview', () => visibleGraph(graph, 'ALL', false, 400, 1000))
assert.ok(view.nodes.length <= 400 && view.edges.length <= 1000)
const focus = measure('6-hop context', () => localContext(graph, 'node-0', 6))
measure('bounded focused rendering', () => visibleGraph(graph, 'ALL', true, 400, 1000, focus))
measure('40 collapsed roots', () => visibleGraph(graph, 'ALL', false, 400, 1000, undefined, new Set(graph.nodes.slice(0, 40).map(node => node.id))))
const matches = measure('identity search', () => matchingNodes(graph, 'node-49999'))
assert.equal(matches[0].id, 'node-49999')
// Timings are machine-specific observations, not a browser-frame SLA.
