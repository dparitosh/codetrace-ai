import { domainColors, domainOf, type TraceNode } from './types'

export type NodeColorMode = 'classification' | 'domain'
export interface NodeClassification { key: string; label: string; color: string; glyph: string }
const classes: Record<string, Omit<NodeClassification, 'key'>> = {
  repository: { label: 'Repository', color: '#0e7490', glyph: 'R' },
  package: { label: 'Package', color: '#92400e', glyph: 'P' },
  module: { label: 'Module', color: '#7c3aed', glyph: 'M' },
  file: { label: 'Source file', color: '#2563eb', glyph: 'F' },
  class: { label: 'Class', color: '#be185d', glyph: 'C' },
  namespace: { label: 'Namespace', color: '#92400e', glyph: 'N' },
  struct: { label: 'Struct', color: '#b45309', glyph: 'St' },
  interface: { label: 'Interface', color: '#a21caf', glyph: 'I' },
  enum: { label: 'Enum', color: '#7c3aed', glyph: 'E' },
  union: { label: 'Union', color: '#c2410c', glyph: 'U' },
  record: { label: 'Record', color: '#9d174d', glyph: 'Rc' },
  function: { label: 'Function', color: '#047857', glyph: 'ƒ' },
  method: { label: 'Method', color: '#0f766e', glyph: 'm' },
  variable: { label: 'Variable', color: '#c2410c', glyph: 'v' },
  symbol: { label: 'Symbol', color: '#475569', glyph: 'S' },
  external_symbol: { label: 'External symbol', color: '#64748b', glyph: 'X' },
  requirement: { label: 'Requirement', color: '#6d28d9', glyph: 'Q' },
  requirement_collection: { label: 'Requirement collection', color: '#4c1d95', glyph: 'QC' },
  architecture: { label: 'Architecture resource', color: '#0f766e', glyph: 'A' },
  change_request: { label: 'Change request', color: '#9a3412', glyph: 'Δ' },
  test: { label: 'Test case', color: '#166534', glyph: 'T' },
  test_plan: { label: 'Test plan', color: '#15803d', glyph: 'TP' },
  test_script: { label: 'Test script', color: '#115e59', glyph: 'TS' },
  test_execution_record: { label: 'Test execution', color: '#14532d', glyph: 'TE' },
  test_result: { label: 'Test result', color: '#3f6212', glyph: 'TR' },
  tracked_resource: { label: 'Tracked resource', color: '#be123c', glyph: 'TRS' },
  configuration: { label: 'Configuration', color: '#0369a1', glyph: 'CFG' },
  resource_shape: { label: 'Resource shape', color: '#4338ca', glyph: 'SH' },
  build: { label: 'Build', color: '#1d4ed8', glyph: 'B' },
  sbom_component: { label: 'SBOM component', color: '#a16207', glyph: 'SB' },
  product: { label: 'Product', color: '#9d174d', glyph: 'PD' },
  feature: { label: 'Feature', color: '#a21caf', glyph: 'FT' },
  variant: { label: 'Variant', color: '#86198f', glyph: 'V' },
  external_resource: { label: 'External resource', color: '#475569', glyph: 'EX' },
}

export function classifyNode(node: TraceNode): NodeClassification {
  const declaration = String(node.properties.declaration_kind || '')
  const nativeKind = ['struct', 'interface', 'enum', 'union', 'record'].find(kind => declaration.startsWith(kind + '_'))
  const key = node.type === 'class' && nativeKind ? nativeKind : node.type === 'package' && node.properties.classification === 'namespace' ? 'namespace' : node.type || 'unknown'
  return { key, ...(classes[key] || { label: key.replace(/_/g, ' '), color: '#475569', glyph: '?' }) }
}
export function nodeFill(node: TraceNode, mode: NodeColorMode = 'classification') {
  return mode === 'classification' ? classifyNode(node).color : domainColors[domainOf(node)] || domainColors.EXTERNAL
}
export function nodeGlyphColor(node: TraceNode, mode: NodeColorMode = 'classification') {
  const rgb = nodeFill(node, mode).slice(1).match(/../g)!.map(value => parseInt(value, 16) / 255)
  const linear = rgb.map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
  const luminance = .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
  return luminance > .179 ? '#000000' : '#ffffff'
}
export function nodeLegend(nodes: TraceNode[], mode: NodeColorMode) {
  const entries = new Map<string, { key: string; label: string; color: string; glyph: string; count: number }>()
  for (const node of nodes) {
    const classification = classifyNode(node)
    const key = mode === 'classification' ? classification.key : domainOf(node)
    const current = entries.get(key)
    if (current) current.count++
    else entries.set(key, { key, label: mode === 'classification' ? classification.label : key,
      glyph: mode === 'classification' ? classification.glyph : '', color: nodeFill(node, mode), count: 1 })
  }
  return [...entries.values()].sort((a, b) => a.label.localeCompare(b.label))
}
