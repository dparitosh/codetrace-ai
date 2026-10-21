export interface TraceNode { id: string; label: string; type: string; properties: Record<string, any> }
export interface TraceEdge { source: string; target: string; type: string; properties: Record<string, any> }
export interface TraceGraph {
  nodes: TraceNode[]
  edges: TraceEdge[]
  metadata: Record<string, any>
  architecture_audit?: Record<string, any>
  source_assessments?: {
    source_digest: string
    summary: { total_files: number; total_lines: number }
    quality: { overall_score: number | null; grade: string; metrics: { name: string; value: number | null; status: string; description: string }[]; recommendations: string[] }
    security: { total_findings: number; files_scanned: number; truncated: boolean; findings: { file: string; line: number; severity: string; description: string; rule: string }[] }
  }
  trs_events?: { id: string; resource_uri: string; action: string; order: number; at: string; provider_id: string }[]
  pipeline_runs?: { id: string; label: string; status: string; revision: string; branch: string; at: string; matches_revision: boolean }[]
}
export interface Catalog {
  sources: { id: string; label: string; kind: string; ref: string | null }[]
  providers: { id: string; label: string; domain: string; transport: string; credential_configured: boolean | null; allow_writes?: boolean }[]
  link_predicates?: string[]
  pipelines: { id: string; label: string; platform: string; repository_id: string }[]
  ai: { provider: string; model: string; timeout_seconds: number }
  settings: { request_timeout_seconds: number; render_nodes: number; render_edges: number; collaboration_timeout_seconds?: number }
  configuration: string
}
export interface CompanionAnswer {
  agent_id?: string
  highlight_ids?: string[]
  trace?: { step: number; tool: string; status: string; resource_ids: string[]; elapsed_ms: number; arguments: Record<string, unknown> }[]
  similar_resources?: { node_id: string; label: string; score: number; lexical_overlap: number; structural_overlap: number; method: string }[]
  recommendations?: { kind: string; node_id?: string; provider_id?: string; message: string; basis: string }[]
  answer: string; mode: string; model: string | null; warning: string | null; snapshot_id: string
  citations: { citation_id: string; node_id: string; label: string; type: string; domain: string; path?: string; line?: number }[]
}

export const domainColors: Record<string, string> = {
  CODE: '#687fa1', AM: '#0e9c91', RM: '#7963bd', CM: '#d89239', QM: '#548f65',
  TRS: '#d26873', CONFIG: '#69899e', SCHEMA: '#778590', CI: '#548bc4', SBOM: '#ae784b', EXTERNAL: '#9ba5af',
}
const typeDomains: Record<string, string> = {
  requirement: 'RM', requirement_collection: 'RM', architecture: 'AM', change_request: 'CM',
  test: 'QM', test_plan: 'QM', test_script: 'QM', test_result: 'QM', test_execution_record: 'QM',
  tracked_resource: 'TRS', configuration: 'CONFIG', resource_shape: 'SCHEMA', build: 'CI',
  sbom_component: 'SBOM', external_resource: 'EXTERNAL',
}
export const domainOf = (node: TraceNode) => String(node.properties.domain || typeDomains[node.type] || 'CODE').trim().toUpperCase()
export const relationLabel = (value: string) => value.split('#').pop()?.split(':').pop() || value
