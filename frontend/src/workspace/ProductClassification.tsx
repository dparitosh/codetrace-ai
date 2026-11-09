export type Classification = {
  status: string; family: string
  capabilities: { id: string; label: string }[]
  features: { id: string; label: string; capability_id: string; kind: string }[]
  coverage: { eligible_files: number; files_with_configured_evidence: number; functions_with_configured_evidence: number; files_requiring_classification: number; unmapped_features: string[] }
  mappings: { artifact_id: string; path: string; kind: string; feature_id: string; status: string; basis: string }[]
  artifact_groups?: { feature_ids: string[]; file_count: number; function_count: number }[]
  operations: { id: string; method: string; path: string; feature_ids: string[] }[]
  lexical_proposals: { artifact_id: string; path: string; feature_id: string; similarity: number; matched_terms: string[] }[]
  configurations: { id: string; status: string; errors: string[] }[]
  feature_similarity: { source: string; target: string; coefficient: number | null; shared_features: string[] }[]
  diagnostics: string[]; limitations: string[]; preview_totals?: Record<string, number>
  ai_review?: { capabilities?: {id:string;label:string;description:string;citation_ids:string[]}[]; features?: {id:string;label:string;description:string;capability_id:string;citation_ids:string[]}[]; status: string; reason?: string; validation?: string; evidence_sent?: number; evidence_total?: number; proposals?: { artifact_id: string; feature_id: string; rationale: string; citation_ids: string[] }[] }
  ai_evidence?: { id: string; artifact_id: string; path: string; kind?: string }[]
}

export default function ProductClassification({ data, busy, stale, onAI, onDraft, onInspect }: {
  data: Classification; busy: boolean; stale: boolean; onAI: () => void
  onDraft: (feature: string, path: string, functionId?: string) => void; onInspect: (id: string) => void
}) {
  return <section aria-label="Capability and feature assessment"><h2>{data.family || 'Product family not supplied'}</h2>
    <p>{data.coverage.files_with_configured_evidence}/{data.coverage.eligible_files} files have configured feature evidence; {data.coverage.functions_with_configured_evidence} functions have configured or file-derived mappings. {data.coverage.files_requiring_classification} files require classification.</p>
    <p>Configured mappings are declarations. Proposed matches require review. Deployment cells remain a separate structural view.</p>
    <h3>Capabilities and features</h3>{data.capabilities.map(cap=><article key={cap.id}><strong>{cap.label}</strong><ul>{data.features.filter(f=>f.capability_id===cap.id).map(f=><li key={f.id}>{f.label} ({f.id}) · {f.kind}</li>)}</ul></article>)}
    {!data.features.length && <p role="status">Supply capability and feature definitions, or request a provisional AI taxonomy from bounded source metadata. Review it before using it as product context.</p>}
    <h3>Groups with the same configured feature profile</h3><p>Artifacts with the same declared feature set form a group. This is separate from dependency cells and does not establish interchangeable implementations.</p>
    {data.artifact_groups?.map(group=><p key={group.feature_ids.join('|')}>{group.feature_ids.join(' + ')}: {group.file_count} files · {group.function_count} functions</p>)}
    <h3>Configured feature-to-artifact matrix</h3><p>Up to 200 mappings shown; full deterministic assessment is included in approved export.</p>
    <div className="incidence-scroll"><table><thead><tr><th scope="col">Artifact</th><th scope="col">Feature</th><th scope="col">Evidence scope</th></tr></thead><tbody>{data.mappings.map(m=><tr key={`${m.artifact_id}-${m.feature_id}-${m.status}`}><th scope="row"><button onClick={()=>onInspect(m.artifact_id)}>{m.path} · {m.kind}</button></th><td>{m.feature_id}</td><td>{m.status}: {m.basis}</td></tr>)}</tbody></table></div>
    <h3>OpenAPI contract evidence</h3><p>{data.preview_totals?.operations ?? data.operations.length} observed operations. Operation-to-feature declarations do not prove a handler implementation.</p>
    <div className="incidence-scroll"><table><thead><tr><th scope="col">Operation</th><th scope="col">Feature</th></tr></thead><tbody>{data.operations.map(op=><tr key={op.id}><th scope="row">{op.method} {op.path}<small>{op.id}</small></th><td>{op.feature_ids.join(', ') || 'Requires classification'}</td></tr>)}</tbody></table></div>
    <h3>Product configuration checks</h3>{!data.configurations.length && <p>No product variants supplied.</p>}{data.configurations.map(p=><article key={p.id}><strong>{p.id}: {p.status}</strong><ul>{p.errors.map(e=><li key={e}>{e}</li>)}</ul><p>Build and source tests have not been run by this assessment.</p></article>)}
    <h3>Declared feature similarity</h3>{data.feature_similarity.map(pair=><p key={`${pair.source}-${pair.target}`}>{pair.source} ↔ {pair.target}: {pair.coefficient===null?'Insufficient feature evidence':pair.coefficient.toFixed(3)} · shared: {pair.shared_features.join(', ') || 'none'}</p>)}
    <h3>Classification proposals</h3><p>Lexical score is Jaccard overlap of artifact names and supplied feature/document terms; it is not a probability or behavioral similarity.</p>
    {data.lexical_proposals.slice(0,50).map(p=><article key={p.artifact_id}><strong>{p.path} → {p.feature_id}</strong><p>Score {p.similarity.toFixed(3)} · observed terms: {p.matched_terms.join(', ')}</p><button disabled={busy || stale} onClick={()=>onDraft(p.feature_id,p.path)}>Add to draft product context</button></article>)}
    <p>Requesting AI sends bounded source names, observed API operation metadata and supplied feature definitions to the configured AI provider. No full source files, raw OpenAPI documents, keys or document bodies are sent. AI proposals are temporary; exports contain deterministic mappings only.</p>
    <button disabled={busy || stale} onClick={onAI}>Request AI classification proposals</button>
    {data.ai_review && <><p role="status">{data.ai_review.status}: {data.ai_review.reason || data.ai_review.validation} {data.ai_review.evidence_sent!==undefined && `Evidence scope ${data.ai_review.evidence_sent}/${data.ai_review.evidence_total}.`}</p>{data.ai_review.features?.map(f=><article key={f.id}><strong>Proposed feature: {f.label} ({f.id})</strong><p>{f.description}</p><p>Proposed capability: {f.capability_id} · citations: {f.citation_ids.map(id=>`[${id}]`).join(' ')}</p><button disabled={busy || stale} onClick={()=>onDraft(f.id,'')}>Add proposed feature to draft context</button></article>)}{data.ai_review.proposals?.map((p,i)=>{
      const evidence=data.ai_evidence?.find(e=>e.artifact_id===p.artifact_id)
      return <article key={i}><strong>{evidence?.path || p.artifact_id} {evidence?.kind==='function'?p.artifact_id:''} → {p.feature_id}</strong><p>{p.rationale}</p><p>Citations: {p.citation_ids.map(id=>`[${id}]`).join(' ')}</p>{evidence && <button disabled={busy || stale} onClick={()=>onDraft(p.feature_id,evidence.path,evidence.kind==='function'?evidence.artifact_id:undefined)}>Add to draft product context</button>}</article>
    })}</>}
    {!!data.diagnostics.length && <div role="alert"><h3>Unresolved mappings</h3><ul>{data.diagnostics.map((d,i)=><li key={i}>{d}</li>)}</ul></div>}
    <details><summary>Classification limitations</summary><ul>{data.limitations.map(l=><li key={l}>{l}</li>)}</ul></details>
  </section>
}
