import { useEffect, useRef, useState } from 'react'
import { workspaceRequest, type ReviewRecord } from '../reviewSession'
import type { Catalog, TraceNode } from './types'
import './productLine.css'
import VisualReportPreview, { type VisualReport } from './VisualReportPreview'
import ProductClassification, { type Classification } from './ProductClassification'

type Analysis = {
  classification: Classification
  product_line: { status: string; feature_units: Record<string,string[]>; unmapped_units: string[]; required_review: string[]; engineering_plan: { stage: string; action: string; gate: string }[] }
  file_groups: { id: string; units: string[]; current: number; projected: number }[]
  algorithm: string; baseline: { files: number; eligible_files: number; excluded_files: number; physical_lines: number; functions: number }
  projection: { planning: { files: number; lines: number }; upper: { files: number; lines: number }; basis: string }
  cells: { id: string; units: string[] }[]; units: { id: string; kind: string; features: string[] }[]
  roc: { passes: number; converged: boolean; columns: string[] }
  candidates: { id: string; kind: string; retained: any; copies: any[]; net_upper_lines: number; files_upper: number; evidence: string }[]
  candidate_count: number; candidates_truncated: boolean
  recommendations: { path: string; kind: string; units: string[]; advice: string; cross_cells: number }[]
  diagnostics: { unit: string; entrypoints: string[]; status: string }[]
  matrices: { files: { path: string; node_id: string; lines: number; memberships: string[] }[]; functions: { id: string; name: string; path: string; file_derived_units: string[]; observed_call_units: string[]; lines: number | null }[] }
  preview: { table_totals: Record<string, number>; recommendation_total: number }
  coverage: { unresolved_dependency_count: number; fingerprinted_functions: number; calls_resolved: number; calls_total: number }
  limitations: string[]; receipt: { analysis_sha256: string; source_revision: string | null; snapshot_id: string; test_status: string }
}
export default function ProductLinePanel({ review, catalog, onSelect }: { review: ReviewRecord | null; catalog: Catalog | null; onSelect: (node: TraceNode) => void }) {
  const [units, setUnits] = useState('[]'), [adoption, setAdoption] = useState(50), [wrapper, setWrapper] = useState(3)
  const [tab, setTab] = useState('summary'), [matrix, setMatrix] = useState('files'), [query, setQuery] = useState('')
  const [data, setData] = useState<Analysis | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [stale, setStale] = useState(false)
  const [minimumLines, setMinimumLines] = useState(8), [similarity, setSimilarity] = useState(0.65)
  const [productContext,setProductContext]=useState('{}')
  const [includeLLM,setIncludeLLM]=useState(true)
  const [contracts,setContracts]=useState<{id:string;document:Record<string,unknown>}[]>([])
  const [report,setReport]=useState<VisualReport|null>(null), [reportOpen,setReportOpen]=useState(false)
  const reportTrigger=useRef<HTMLButtonElement>(null)
  useEffect(()=>{if(!reportOpen && report)reportTrigger.current?.focus()},[reportOpen,report])
  const generation = useRef(0)
  useEffect(() => () => { generation.current++ }, [])
  const perform = async (action: 'analyze' | 'export' | 'ai' | 'report' = 'analyze') => {
    if (!review || !catalog || busy) return
    if(action==='report' && report && !stale){setReportOpen(true);return}
    const current = ++generation.current
    setBusy(true); setError('')
    try {
      const parsed = JSON.parse(units)
      if (!Array.isArray(parsed)) throw new Error('Units must be a JSON array.')
      const payload = { include_llm:includeLLM, product_context:JSON.parse(productContext), openapi_artifacts:contracts, review_id: review.id, units: parsed, adoption_rate: adoption / 100, wrapper_lines: wrapper, minimum_function_lines: minimumLines, cell_similarity: similarity }
      if(action==='report'){
        const result=await workspaceRequest<VisualReport>('optimization/report',payload,catalog.settings.request_timeout_seconds,review.sessionToken)
        if(generation.current!==current)return
        if(result.receipt.review_result_digest!==review.result_digest || (result.receipt.snapshot_id ?? null)!==(review.result?.metadata.snapshot_id ?? null))throw new Error('Report belongs to a different source snapshot.')
        setReport(result);setReportOpen(true);setStale(false)
      } else if (action==='ai') {
        const result=await workspaceRequest<{classification:Classification;receipt:Analysis['receipt']}>('optimization/classify-ai',payload,catalog.settings.request_timeout_seconds+5,review.sessionToken)
        if(generation.current!==current)return
        if(result.receipt.snapshot_id!==review.result?.metadata.snapshot_id)throw new Error('AI assessment returned a different source snapshot.')
        setData(old=>old?{...old,classification:result.classification}:old)
      } else if (action==='export') {
        const result = await workspaceRequest<{ filename: string; archive_base64: string }>('optimization/export', payload, catalog.settings.request_timeout_seconds, review.sessionToken)
        if (generation.current !== current) return
        const bytes = Uint8Array.from(atob(result.archive_base64), character => character.charCodeAt(0))
        const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }))
        const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      } else {
        const result = await workspaceRequest<Analysis>('optimization/analyze', payload, catalog.settings.request_timeout_seconds, review.sessionToken)
        if (generation.current !== current) return
        if (result.receipt.snapshot_id !== review.result?.metadata.snapshot_id) throw new Error('Optimization returned a different source snapshot.')
        setData(result); setReport(null); setReportOpen(false); setStale(false)
      }
    } catch (cause) { if (generation.current === current) setError(cause instanceof Error ? cause.message : 'Optimization could not complete') }
    finally { if (generation.current === current) setBusy(false) }
  }
  const change = () => {setStale(true);setReport(null);setReportOpen(false)}
  const addDraft = (featureId:string,path:string,functionId?:string) => {
    try {
      const context=JSON.parse(productContext)
      context.features ??= JSON.parse(JSON.stringify(data?.classification.features || []))
      context.capabilities ??= JSON.parse(JSON.stringify(data?.classification.capabilities || []))
      let feature=context.features.find((f:{id:string})=>f.id===featureId)
      if(!feature){
        const suggested=data?.classification.ai_review?.features?.find(f=>f.id===featureId)
        if(!suggested)throw new Error('No supplied or proposed feature matches this identifier.')
        feature={id:suggested.id,label:suggested.label,description:suggested.description,capability_id:suggested.capability_id,kind:'optional'}
        if(!context.capabilities.some((c:{id:string})=>c.id===feature.capability_id)){
          const cap=data?.classification.ai_review?.capabilities?.find(c=>c.id===feature.capability_id)
          if(!cap)throw new Error('Missing capability definition for proposed feature.')
          context.capabilities.push({id:cap.id,label:cap.label,description:cap.description})
        }
        context.features.push(feature)
      }
      if(functionId)feature.function_ids=[...new Set([...(feature.function_ids || []),functionId])]
      else if(path)feature.paths=[...new Set([...(feature.paths || []),path])]
      setProductContext(JSON.stringify(context,null,2));change()
    }catch(cause){setError(cause instanceof Error?cause.message:'Invalid product context')}
  }
  const uploadContracts = async (files:FileList|null) => {
    if(!files)return
    const current=++generation.current
    setBusy(true);setError('')
    try{
      if(files.length>8)throw new Error('Select at most eight OpenAPI JSON documents.')
      const next=[]
      for(const [index,file] of Array.from(files).entries()){
        if(file.size>1000000)throw new Error('Each OpenAPI JSON document must be at most 1 MB.')
        next.push({id:`contract-${index+1}`,document:JSON.parse(await file.text())})
      }
      if(generation.current===current){setContracts(next);change()}
    }catch(cause){if(generation.current===current)setError(cause instanceof Error?cause.message:'Invalid OpenAPI JSON')}
    finally{if(generation.current===current)setBusy(false)}
  }
  if (!review) return <section className="plain-panel"><p>Analyze or synchronize a configurable source folder to assess its refactoring opportunities.</p></section>
  const filteredFiles = data?.matrices.files.filter(row => row.path.toLowerCase().includes(query.toLowerCase())) || []
  const filteredFunctions = data?.matrices.functions.filter(row => `${row.name} ${row.path}`.toLowerCase().includes(query.toLowerCase())) || []
  return <section className="product-line" aria-label="Product-line optimization">
    <p>Group technology → incidence matrix → cellular grouping → product-line recommendations. Projections require contract review and implementation before savings can be claimed.</p>
    <details><summary>Product context and API contract evidence</summary>
      <label>Product context (JSON)<textarea rows={10} value={productContext} disabled={busy} onChange={event=>{setProductContext(event.target.value);change()}} /></label>
      <p>Define family, capabilities, features and products. Features support paths (relative glob selectors), exact function_ids, operation_ids, requires/excludes and alternative_group. Documents support id, title, text and feature_ids. These are supplied declarations; they do not establish semantic correctness. An empty model uses centrally configured OPTIMIZATION_PRODUCT_CONTEXT if present.</p>
      <details><summary>Generic product model example</summary><pre>{JSON.stringify({family:'Example family',capabilities:[{id:'reporting',label:'Reporting'}],features:[{id:'export',label:'Export report',capability_id:'reporting',kind:'optional',paths:['src/reporting/*'],operation_ids:['exportReport']}],products:[{id:'standard',features:['export']}]},null,2)}</pre></details>
      <label>OpenAPI JSON documents<input type="file" accept=".json,application/json" multiple disabled={busy} onChange={event=>{void uploadContracts(event.target.files)}} /></label>
      <p>{contracts.length} contract documents selected. JSON only, at most eight documents and 1 MB each. No external references or server URLs are fetched.</p>
      <button disabled={busy || !contracts.length} onClick={()=>{setContracts([]);change()}}>Clear contract documents</button>
    </details>
    <details><summary>Product/deployment units and projection assumptions</summary>
      <label>Units (JSON)<textarea value={units} onChange={event => { setUnits(event.target.value); change() }} rows={5} disabled={busy} /></label>
      <p>Use exact relative file paths or callable IDs from this snapshot. Example: {JSON.stringify([{ id: 'variant-a', entrypoints: ['src/main.py'], features: ['reporting'], kind: 'product_variant' }])}. An empty array uses centrally configured OPTIMIZATION_UNITS or structural directory groups; those are not deployed-service evidence.</p>
      <label>Planning adoption (%)<input type="number" min={0} max={100} value={adoption} disabled={busy} onChange={event => { setAdoption(Number(event.target.value)); change() }} /></label>
      <label>Retained wrapper lines per duplicate declaration<input type="number" min={0} max={100} value={wrapper} disabled={busy} onChange={event => { setWrapper(Number(event.target.value)); change() }} /></label>
      <label>Minimum declaration lines<input type="number" min={3} max={1000} value={minimumLines} disabled={busy} onChange={event => { setMinimumLines(Number(event.target.value)); change() }} /></label>
      <label>Cell overlap threshold<input type="number" min={0.01} max={1} step={0.05} value={similarity} disabled={busy} onChange={event => { setSimilarity(Number(event.target.value)); change() }} /></label>
    </details>
    <label className="report-ai-option"><input type="checkbox" checked={includeLLM} disabled={busy} onChange={event=>{setIncludeLLM(event.target.checked);change()}} /> Include LLM recommendations using the configured AI provider</label>
    <small>This sends bounded names, candidate metadata and computed projections; full source is not sent. A fresh advisory review is generated for preview/export. Unavailable models are disclosed.</small>
    <div className="product-line-actions"><button ref={reportTrigger} onClick={() => perform('report')} disabled={busy || !catalog}>Open visual report</button><button onClick={() => perform()} disabled={busy}>Run custom analysis</button><button onClick={() => perform('export')} disabled={busy || (!data && !report) || stale || review.status !== 'approved'}>Export approved report & evidence</button></div>
    {reportOpen && report && <VisualReportPreview report={report} approved={review.status==='approved'} exporting={busy} onClose={()=>setReportOpen(false)} onExport={()=>{void perform('export')}} />}
    {review.status !== 'approved' && <small>Analysis is available now; approve the exact source snapshot in Review center before exporting.</small>}
    {busy && <p role="status">Analyzing the retained source snapshot…</p>}{error && <p role="alert">{error}</p>}
    {stale && data && <p role="status">Assumptions changed. Run the analysis again before using or exporting these projections.</p>}
    {data && <>
      <div role="group" aria-label="Optimization views" className="product-line-actions">{[['summary','Projection'],['matrices','Incidence matrices'],['candidates','Refactoring candidates'],['sple','Product-line engineering'],['classification','Capabilities & features']].map(([id,label]) => <button key={id} aria-pressed={tab===id} onClick={() => setTab(id)}>{label}</button>)}</div>
      {tab==='summary' && <><h2>Projected opportunity — no source changes applied</h2><p>{data.baseline.eligible_files} eligible files / {data.baseline.files} scanned · {data.baseline.physical_lines.toLocaleString()} physical lines · {data.baseline.excluded_files} test/fixture files excluded.</p>
        <FileGroupChart groups={data.file_groups || []} />
        <p>Projected declaration-line removal: planning {data.projection.planning.lines.toLocaleString()} / upper candidate envelope {data.projection.upper.lines.toLocaleString()}. File counts change only for whole-file removal candidates.</p><p>{data.projection.basis}</p><p>Observed callable links: {data.coverage.calls_resolved}/{data.coverage.calls_total}. Unresolved/external dependencies: {data.coverage.unresolved_dependency_count}. Fingerprinted declarations: {data.coverage.fingerprinted_functions}.</p>
        <details><summary>Analysis limits and receipt</summary><ul>{data.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>Algorithm {data.algorithm} · {data.roc.passes} ROC passes · {data.roc.converged ? 'stable ordering' : 'bounded ordering; not converged'}</p><p>Tests: {data.receipt.test_status}. Revision: {data.receipt.source_revision || 'Not established'}</p><code>{data.receipt.analysis_sha256}</code></details></>}
      {tab==='matrices' && <><label>Matrix<select value={matrix} onChange={event => setMatrix(event.target.value)}><option value="files">File × unit</option><option value="functions">Function × unit</option></select></label><label>Filter preview<input type="search" value={query} onChange={event => setQuery(event.target.value)} /></label><p>Showing a filtered preview of the first 200 / {data.preview.table_totals[matrix]} rows. Export contains all analyzed rows. Function incidence is file-derived; observed call membership is reported separately.</p>
        <div className="incidence-scroll"><table><thead><tr><th scope="col">Source</th>{matrix==='functions' && <th scope="col">Observed call units</th>}{data.roc.columns.map(id => <th key={id} scope="col">{id}</th>)}</tr></thead><tbody>{matrix==='files' ? filteredFiles.map(row => <tr key={row.node_id}><th scope="row"><button onClick={() => { const node=review.result?.nodes.find((node: TraceNode) => node.id===row.node_id); if(node) onSelect(node) }}>{row.path}</button></th>{data.roc.columns.map(id => <td key={id} className={row.memberships.includes(id)?'incidence-one':''}>{row.memberships.includes(id)?1:0}</td>)}</tr>) : filteredFunctions.map(row => <tr key={row.id}><th scope="row">{row.name}<small>{row.path}</small></th><td>{row.observed_call_units.join(', ') || 'Not established'}</td>{data.roc.columns.map(id => <td key={id} className={row.file_derived_units.includes(id)?'incidence-one':''}>{row.file_derived_units.includes(id)?1:0}</td>)}</tr>)}</tbody></table></div></>}
      {tab==='candidates' && <><p>{data.candidates.length}/{data.candidate_count} candidates retained{data.candidates_truncated ? '; configured limit reached' : ''}. These are review hypotheses, not approved edits.</p>{!data.candidates.length && <p>No eligible duplicate fingerprints found. This does not prove the code is optimal; check parser coverage and scope.</p>}{data.candidates.map(item => <details key={item.id}><summary>{item.kind.replace(/_/g,' ')} · up to {item.net_upper_lines} lines / {item.files_upper} files</summary><p>{item.evidence}</p><pre>{JSON.stringify({ retained:item.retained, copies:item.copies },null,2)}</pre></details>)}</>}
      {tab==='classification' && data.classification && <ProductClassification data={data.classification} busy={busy} stale={stale} onAI={()=>{void perform('ai')}} onDraft={addDraft} onInspect={id=>{const node=review.result?.nodes.find((n:TraceNode)=>n.id===id);if(node)onSelect(node)}} />}
      {tab==='sple' && <><p>Feature model: {data.product_line.status.replace(/_/g,' ')}. Explicit feature mapping is required before product configuration claims.</p><ol>{data.product_line.engineering_plan.map(step => <li key={step.stage}><strong>{step.stage}</strong><p>{step.action}</p><small>Acceptance: {step.gate}</small></li>)}</ol><details><summary>Product-line feature context and required review</summary><pre>{JSON.stringify(data.product_line,null,2)}</pre></details><h2>Candidate cells and variation boundaries</h2><p>Cells use complete-link overlap after custom binary rank-order clustering. Commonality suggests platform candidates; feature meanings and compatibility constraints must be supplied and validated.</p>{data.cells.map(cell => <p key={cell.id}><strong>{cell.id}</strong> · {cell.units.join(', ')}</p>)}<p>{data.preview.recommendation_total} recommendations; first {data.recommendations.length} shown.</p>{data.recommendations.map(item => <article key={item.path}><h3>{item.path}</h3><p>{item.kind.replace(/_/g,' ')} · {item.units.join(', ')} · {item.cross_cells} cells</p><p>{item.advice}</p></article>)}</>}
      {!!data.diagnostics.length && <div role="alert"><h3>Unresolved unit entrypoints</h3>{data.diagnostics.map(item => <p key={item.unit}>{item.unit}: {item.entrypoints.join(', ')}</p>)}<p>Zero membership is incomplete evidence; correct the unit definition before using these cells.</p></div>}
    </>}
  </section>
}

function FileGroupChart({ groups }: { groups: Analysis['file_groups'] }) {
  const step=Math.max(1,Math.ceil(Math.max(1,...groups.map(g=>g.current))/5)), top=step*5
  const width=Math.max(1000,groups.length*130+130), left=80, right=width-30, bottom=380, height=260
  const band=(right-left)/Math.max(1,groups.length), bar=Math.min(36,band*.28)
  return <figure className="file-group-chart"><figcaption>Current and projected file quantities by group</figcaption>
    <p><span className="current-key">■ Current</span> · <span className="projected-key">■ Projected (planning)</span></p>
    <div className="file-group-scroll"><svg width={width} height={535} viewBox={`0 0 ${width} 535`} role="img" aria-label="Current and projected file counts. X-axis: GT cell file groups. Y-axis: file quantity.">
      {[0,1,2,3,4,5].map(tick=>{const y=bottom-height*tick/5;return <g key={tick}><path d={`M${left} ${y}H${right}`} stroke="var(--ct-border,#d9e2ec)"/><text x={left-10} y={y+5} textAnchor="end">{tick*step}</text></g>})}
      <path d={`M${left} 120V${bottom}H${right}`} fill="none" stroke="currentColor"/>
      <text x={22} y={250} transform="rotate(-90 22 250)" textAnchor="middle">File quantity</text>
      {groups.map((group,i)=>{const center=left+band*(i+.5);return <g key={group.id}>{(['current','projected'] as const).map((key,j)=>{
        const value=group[key],h=height*value/top,x=center+(j===0?-bar-3:3)
        return <g key={key}><rect x={x} y={bottom-h} width={bar} height={h} fill={j===0?'#227ea2':'#c38324'}><title>{group.id}: {key} {value}</title></rect><text x={x+bar/2} y={bottom-h-8} textAnchor="middle">{value}</text></g>
      })}<text x={center} y={405} transform={`rotate(25 ${center} 405)`}>{group.id}</text></g>})}
      <text x={width/2} y={505} textAnchor="middle">File groups (GT cells, shared and unmapped)</text>
    </svg></div><p>Each eligible file is counted once. Equal bars mean no supported whole-file reduction.</p>
    <details><summary>File group quantities and deployment units</summary><div className="incidence-scroll"><table><thead><tr><th scope="col">File group</th><th scope="col">Units</th><th scope="col">Current</th><th scope="col">Projected</th></tr></thead><tbody>{groups.map(g=><tr key={g.id}><th scope="row">{g.id}</th><td>{g.units.join(', ') || 'Shared or unresolved membership'}</td><td>{g.current}</td><td>{g.projected}</td></tr>)}</tbody></table></div></details>
  </figure>
}
