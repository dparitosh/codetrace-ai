import { useMemo, useState } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { ClientSideRowModelModule, PaginationModule, TextFilterModule, ModuleRegistry, themeQuartz } from 'ag-grid-community'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'
import { domainOf, TraceGraph, TraceNode } from './types'
import NodeBadge from './NodeBadge'

ModuleRegistry.registerModules([ClientSideRowModelModule, PaginationModule, TextFilterModule])
const tableTheme = themeQuartz.withParams({ backgroundColor: 'var(--ct-surface)', foregroundColor: 'var(--ct-text)', borderColor: 'var(--ct-border)', headerBackgroundColor: 'var(--ct-background)' })

export default function GraphDataTable({ graph, resources, onSelect }: { graph: TraceGraph | null; resources: TraceNode[]; onSelect: (node: TraceNode) => void }) {
  const [tab, setTab] = useState<'resources' | 'relationships'>('resources')
  const [technical, setTechnical] = useState(false)
  const nodes = useMemo(() => new Map(graph?.nodes.map(node => [node.id, node]) ?? []), [graph])
  const visible = useMemo(() => new Set(resources.map(node => node.id)), [resources])
  const rows = useMemo(() => tab === 'resources' ? resources.map(node => ({ id: node.id, label: node.label, type: node.type, domain: domainOf(node), node, evidence: String(node.properties.path ?? node.properties.provider_id ?? ''), properties: JSON.stringify(node.properties) }))
    : (graph?.edges ?? []).filter(edge => visible.has(edge.source) || visible.has(edge.target)).map((edge, index) => ({ id: `${index}:${edge.source}:${edge.target}`, source: nodes.get(edge.source)?.label ?? edge.source, source_id: edge.source, predicate: edge.type, target: nodes.get(edge.target)?.label ?? edge.target, target_id: edge.target, properties: JSON.stringify(edge.properties) })), [tab, resources, graph, nodes, visible])
  const columns = useMemo<ColDef[]>(() => {
    const main: ColDef[] = tab === 'resources'
      ? [{ field: 'label', headerName: 'Resource' }, { field: 'type', headerName: 'Classification', minWidth: 170, cellRenderer: (params: ICellRendererParams) => params.data?.node ? <NodeBadge node={params.data.node} showDomain={false} /> : null }, { field: 'domain', maxWidth: 120 }, { field: 'evidence', flex: 2 }]
      : [{ field: 'source' }, { field: 'predicate' }, { field: 'target' }]
    const identifiers = tab === 'resources' ? [{ field: 'id', headerName: 'Resource ID' }] : [{ field: 'source_id' }, { field: 'target_id' }]
    return technical ? [...main, ...identifiers, { field: 'properties' }] : main
  }, [tab, technical])
  return <section className="graph-data-table" aria-label="Graph data table">
    <div className="ai-action-row" role="group" aria-label="Grid contents"><button aria-pressed={tab === 'resources'} onClick={() => setTab('resources')}>Resources</button><button aria-pressed={tab === 'relationships'} onClick={() => setTab('relationships')}>Relationships</button><label className="technical-columns"><input type="checkbox" checked={technical} onChange={event => setTechnical(event.target.checked)} />IDs & properties</label><small>{rows.length.toLocaleString()} rows · select to inspect{tab === 'relationships' ? ' source resource' : ''}</small></div>
    <div style={{ height: 520, width: '100%' }}><AgGridReact key={tab} theme={tableTheme} rowData={rows} columnDefs={columns} defaultColDef={{ sortable: true, filter: 'agTextColumnFilter', resizable: true, minWidth: 150, flex: 1 }} pagination paginationPageSize={50} paginationPageSizeSelector={[25, 50, 100]} getRowId={params => params.data.id} onRowClicked={event => { const id = tab === 'resources' ? event.data?.id : event.data?.source_id; const node = id ? nodes.get(id) : undefined; if (node) onSelect(node) }} /></div>
  </section>
}
