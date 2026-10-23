import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { changeRequest, type ReviewRecord, useReviewSession } from '../reviewSession'
import type { Catalog, CompanionAnswer, TraceGraph, TraceNode } from './types'
import './changeWorkbench.css'
const InteractiveGraph = lazy(() => import('./InteractiveGraph'))
const GraphDataTable = lazy(() => import('./GraphDataTable'))
const CollaborationPanel = lazy(() => import('./CollaborationPanel'))

const labels = { title: 'Title', problem: 'Observed problem', impact: 'Impact and rationale', scope: 'Change scope',
  proposal: 'Proposed correction', acceptance: 'Acceptance criteria', validation: 'Validation plan', rollback: 'Recovery plan (optional)' }
type Fields = Record<keyof typeof labels, string>
interface Turn { id: string; request_id: string; state: string; question: string; selected_id: string | null; automate: boolean; agent_id: string; error?: string; analyses: { agent_id: string; result: CompanionAnswer }[] }
interface Evidence { id: string; node: TraceNode; captured_at: string; snapshot_id: string; provenance: Record<string, string>; observations: Record<string, string>[]; relationships: TraceGraph['edges']; relationship_count: number; relationships_truncated: boolean; source_findings: unknown[] }
interface Dossier extends Fields { id: string; revision: number; version: number; state: string; snapshot_id: string; snapshot_digest: string;
  selected_id: string | null; evidence: Evidence[]; turns: Turn[]; automation_review_required: boolean;
  context_warnings?: string[];
  audit: { action: string; at: string; note: string }[]; versions: { version: number; digest: string; dossier: Record<string, unknown> }[]; graph?: TraceGraph }
type QueueItem = Pick<Dossier, 'id' | 'revision' | 'version' | 'state' | 'title'>
type Tab = 'conversation' | 'dossier' | 'graph' | 'table' | 'imported'

export default function ChangeWorkbench({ graph, review, catalog, selected, active = true }: { graph: TraceGraph | null; review: ReviewRecord | null; catalog: Catalog | null; selected: TraceNode | null; active?: boolean }) {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [fields, setFields] = useState<Fields | null>(null)
  const [tab, setTab] = useState<Tab>('conversation')
  const [question, setQuestion] = useState('')
  const [agent, setAgent] = useState('trace-explorer')
  const [contextId, setContextId] = useState('')
  const [contextQuery, setContextQuery] = useState('')
  const [seed, setSeed] = useState<TraceNode | null>(null)
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [acknowledged, setAcknowledged] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const generation = useRef(0)
  const pendingRequest = useRef<{ key: string; id: string } | null>(null)
  const pendingCreation = useRef<{ key: string; id: string } | null>(null)
  const session = useReviewSession()
  const sessionToken = useRef(session?.token)
  useEffect(() => setSeed(null), [graph?.metadata.snapshot_id])
  const loadQueue = async () => setQueue(await changeRequest<QueueItem[]>())
  useEffect(() => { let active = true; const invalidate = () => { generation.current++ }
    changeRequest<QueueItem[]>().then(items => { if (active) setQueue(items) }).catch(cause => { if (active) setError(String(cause)) });
    return () => { active = false; invalidate() } }, [])
  useEffect(() => {
    if (sessionToken.current && sessionToken.current !== session?.token) {
      generation.current++; setDossier(null); setFields(null); setQueue([]); setDirty(false); setBusy(false); setError('Session changed. Reopen the durable dossier after starting a session.')
    }
    sessionToken.current = session?.token
  }, [session?.token])
  const accept = (data: Dossier, preserveEdits = false) => {
    setDossier(current => ({ ...data, graph: data.graph || current?.graph }))
    if (!preserveEdits) {
      setFields(Object.fromEntries(Object.keys(labels).map(key => [key, data[key as keyof Fields]])) as Fields)
      setDirty(false)
    }
    setAcknowledged(false)
  }
  const run = async (action: () => Promise<Dossier>, reset = false, clearQuestion = false, preserveEdits = false) => {
    if (busy) return
    const version = ++generation.current
    setBusy(true); setError('')
    try {
      const data = await action()
      if (version !== generation.current) return
      accept(data, preserveEdits)
      if (preserveEdits) setError('Saved state refreshed. Your unsaved edits are retained; compare them with saved state before saving or explicitly discard them.')
      if (clearQuestion) setQuestion('')
      if (reset) { setContextId(data.selected_id || ''); setContextQuery(''); setQuestion(''); setNote(''); setTab('conversation'); setAdvanced(false) }
      await loadQueue()
    } catch (cause) { if (version === generation.current) setError(cause instanceof Error ? cause.message : 'Change workflow failed') }
    finally { if (version === generation.current) setBusy(false) }
  }
  const open = (id: string) => run(() => changeRequest<Dossier>('/' + encodeURIComponent(id)), true)
  const create = () => {
    if (!review) return
    const selectedId = seed?.id || selected?.id || null
    const key = JSON.stringify([review.sessionToken, review.id, selectedId])
    if (pendingCreation.current?.key !== key) pendingCreation.current = { key, id: crypto.randomUUID() }
    const requestId = pendingCreation.current.id
    run(async () => {
      const result = await changeRequest<Dossier>('', { request_id: requestId, review_id: review.id, selected_id: selectedId }, undefined, review.sessionToken)
      pendingCreation.current = null
      return result
    }, true)
  }
  const editable = dossier?.state === 'draft'
  const activeAnalysis = dossier?.turns.some(turn => turn.state === 'processing') || false
  const frozenGraph = dossier?.graph || null
  const contextNode = frozenGraph?.nodes.find(node => node.id === contextId) || null
  const missing = fields ? Object.entries(labels).filter(([key]) => key !== 'rollback' && !fields[key as keyof Fields]?.trim()).map(([, label]) => label) : []
  if (dossier && !dossier.evidence.length) missing.push('Captured evidence')
  const contextMatches = (frozenGraph?.nodes || []).filter(node => `${node.label} ${node.properties.path || ''} ${node.id}`.toLowerCase().includes(contextQuery.toLowerCase()))
  const contextChoices = contextMatches.slice(0, 100)
  if (contextNode && !contextChoices.some(node => node.id === contextNode.id)) contextChoices.unshift(contextNode)
  const save = () => { if (dossier && fields) run(() => changeRequest<Dossier>(`/${dossier.id}/edit`, { revision: dossier.revision, ...fields })) }
  const ask = (automate: boolean, retry?: Turn) => {
    if (!dossier || dirty) return
    const value = retry?.question || question.trim() || (automate ? 'Investigate the selected context, identify evidence gaps, propose software corrections and complete missing dossier sections. Do not execute changes or claim unrun tests passed.' : '')
    if (!value) return
    const selectedId = retry ? retry.selected_id : contextId || null
    const key = JSON.stringify([dossier.id, value, automate, agent, selectedId])
    if (pendingRequest.current?.key !== key) pendingRequest.current = { key, id: crypto.randomUUID() }
    const requestId = retry?.request_id || pendingRequest.current.id
    run(async () => {
      const result = await changeRequest<Dossier>(`/${dossier.id}/conversation`, { revision: dossier.revision, request_id: requestId,
        question: value, selected_id: selectedId, agent_id: retry?.agent_id || agent, automate: retry?.automate ?? automate }, 150)
      pendingRequest.current = null
      return result
    }, false, true)
  }
  const capture = (nodeId: string, turnId = '', agentId = '', citationId = '') => {
    if (dossier) run(() => changeRequest<Dossier>(`/${dossier.id}/evidence`, { revision: dossier.revision, node_id: nodeId, turn_id: turnId, agent_id: agentId, citation_id: citationId }))
  }
  const decide = (action: string) => { if (dossier) run(() => changeRequest<Dossier>(`/${dossier.id}/decision`, { revision: dossier.revision, action, note, acknowledged })) }
  const exportDossier = async () => {
    if (!dossier || busy) return
    const version = ++generation.current
    setBusy(true); setError('')
    try {
      const data = await changeRequest(`/${dossier.id}/export`)
      if (version !== generation.current) return
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `change-dossier-${dossier.id}-v${dossier.version}.json`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) { if (version === generation.current) setError(String(cause)) } finally { if (version === generation.current) setBusy(false) }
  }
  return <section className="change-workbench" aria-label="Conversational change workbench">
    <p>Investigate → capture evidence → complete dossier → local review → approved external submission. Agents propose corrections; they do not edit software or approve changes.</p>
    <div className="change-layout"><aside className="change-queue" aria-label="Local change review queue"><h2>Local review queue</h2>
      <button disabled={busy || dirty || !review} onClick={create}>New dossier from active snapshot</button>
      {!review && <small>Synchronize a source to create a dossier. Existing cases remain available.</small>}
      <button disabled={busy || dirty} onClick={() => { loadQueue().catch(cause => setError(String(cause))) }}>Refresh queue</button>
      {queue.map(item => <button key={item.id} className={dossier?.id === item.id ? 'selected' : ''} disabled={busy || dirty} onClick={() => open(item.id)}><strong>{item.title}</strong><small>v{item.version} · {item.state.replace(/_/g, ' ')}</small></button>)}
      {!queue.length && <p>No local change dossiers yet.</p>}<small>Shared local workspace. Recorded reviewer labels are not independent account authentication.</small>
    </aside><div className="change-case">
      {error && <p role="alert" className="workspace-alert">{error} <button disabled={busy} onClick={() => dossier ? run(() => changeRequest<Dossier>('/' + encodeURIComponent(dossier.id)), false, false, dirty) : loadQueue().catch(cause => setError(String(cause)))}>Refresh saved state</button></p>}
      {busy && <p role="status">Working… agent analysis may continue if the browser request times out. Refresh saved state before retrying.</p>}
      <div className="change-tabs" role="group" aria-label="Change workspace views">{(['conversation', 'dossier', 'graph', 'table', 'imported'] as Tab[]).map(value => <button key={value} aria-pressed={tab === value} onClick={() => setTab(value)}>{({ conversation: 'Conversation', dossier: 'Dossier & review', graph: 'Evidence graph', table: 'Data grid', imported: 'Imported changes' })[value]}</button>)}</div>
      {dossier && <header><h2>{dossier.title}</h2><p>Version {dossier.version} · {dossier.state.replace(/_/g, ' ')} · frozen snapshot {String(dossier.snapshot_id).slice(0, 12)} · {dossier.evidence.length} evidence items</p>
        {review && review.result_digest !== dossier.snapshot_digest && <p role="status">This dossier retains its original evidence. The active source snapshot is different.</p>}</header>}
      {dirty && <><p role="status">Unsaved dossier edits. Save before analysis, capture, review or switching dossiers.</p><button disabled={busy} onClick={() => { if (dossier) { accept(dossier); setError('') } }}>Discard unsaved edits and use saved dossier</button><details><summary>Compare saved dossier fields</summary><pre>{JSON.stringify(Object.fromEntries(Object.keys(labels).map(key => [key, dossier?.[key as keyof Fields]])), null, 2)}</pre></details></>}
      {dossier?.context_warnings?.map(warning => <p role="status" key={warning}>{warning}</p>)}
      {activeAnalysis && <p role="status">A saved analysis is processing. Refresh saved state to recover its outcome; interrupted analyses become retryable after their deadline.</p>}
      {!dossier && tab !== 'imported' && <div className="plain-panel"><h2>Start an evidence-backed change</h2><p>Open a saved dossier or create one from the active snapshot{(seed || selected) ? ` for ${(seed || selected)?.label}` : ''}. The conversation, evidence and submitted versions survive session expiry.</p></div>}
      <Suspense fallback={<p role="status">Loading evidence view…</p>}>
      {tab === 'imported' && <><p>Provider change requests are imported evidence; they are distinct from the local review queue. Select a resource to seed a new dossier.</p>{seed && <p>Selected context: {seed.label}</p>}<GraphDataTable graph={graph} resources={graph?.nodes.filter(node => node.properties.domain === 'CM' || node.type === 'change_request') || []} onSelect={setSeed} /></>}
      {dossier && tab === 'conversation' && <>
        <div className="change-context"><label>Filter evidence context<input value={contextQuery} onChange={event => setContextQuery(event.target.value)} type="search" /></label>
          <label>Conversation context<select value={contextId} disabled={busy || !editable} onChange={event => setContextId(event.target.value)}><option value="">Whole frozen snapshot</option>{contextChoices.map(node => <option key={node.id} value={node.id}>{node.label} · {node.properties.path || node.type}</option>)}</select></label>
          {contextMatches.length > 100 && <small>Showing 100 matches; refine the filter.</small>}
          <button disabled={busy || dirty || !editable || activeAnalysis || !contextId} onClick={() => capture(contextId)}>Capture selected resource</button></div>
        <div className="change-transcript" aria-label="Dossier conversation">{!dossier.turns.length && <p>Describe the observed problem, or run the agents to investigate the selected graph context and draft the dossier.</p>}
          {dossier.turns.map(turn => <article key={turn.id}><h3>You</h3><p>{turn.question}</p><small>{turn.state} · {turn.selected_id || 'whole snapshot'}</small>
            {turn.analyses.map(analysis => <section key={analysis.agent_id}><h3>{analysis.agent_id.replace(/-/g, ' ')} · {analysis.result.mode === 'evidence' ? 'graph evidence' : 'agent analysis'}</h3><p className="change-answer">{analysis.result.answer}</p>{analysis.result.warning && <p className="answer-warning">{analysis.result.warning}</p>}
              <div className="change-citations">{analysis.result.citations.map(citation => <div key={citation.citation_id}><span>{citation.citation_id} · {citation.label}</span><button disabled={busy || dirty || !editable || activeAnalysis} onClick={() => capture(citation.node_id, turn.id, analysis.agent_id, citation.citation_id)}>Capture evidence</button><button onClick={() => { setContextId(citation.node_id); setTab('graph') }}>Inspect graph</button></div>)}</div>
              <details><summary>Observed agent tools</summary>{analysis.result.trace?.map(step => <p key={step.step}>{step.step}. {step.tool} · {step.status} · {step.resource_ids.length} resources</p>)}</details>
            </section>)}
            {turn.error && <p role="alert">{turn.error}</p>}{turn.state === 'failed' && <button disabled={busy || dirty || !editable || activeAnalysis} onClick={() => ask(turn.automate, turn)}>Retry saved turn</button>}
          </article>)}
        </div>
        {editable ? <form onSubmit={event => { event.preventDefault(); ask(false) }}><label>Describe the change or ask a follow-up<textarea maxLength={1500} value={question} onChange={event => setQuestion(event.target.value)} disabled={busy || activeAnalysis} /></label>
          <label>Investigation agent<select value={agent} disabled={busy} onChange={event => setAgent(event.target.value)}><option value="trace-explorer">Trace explorer</option><option value="coverage-reviewer">Coverage reviewer</option><option value="change-analyst">Change analyst</option></select></label>
          <button disabled={busy || dirty || activeAnalysis || !question.trim()}>Send question</button><button type="button" disabled={busy || dirty || activeAnalysis} onClick={() => ask(true)}>Run agents · complete & check dossier</button>
          <p>Runs trace, coverage and change agents against pinned evidence. Fills missing sections and updates agent-owned proposals while preserving your edits. Agent suggestions require human review; no source files are changed.</p></form> : <p>This submitted version is frozen. Create a new draft revision to continue the conversation.</p>}
      </>}
      {dossier && fields && tab === 'dossier' && <>
        <div className="change-form">{Object.entries(labels).map(([key, label]) => <label key={key}>{label}<textarea rows={key === 'title' ? 1 : 3} maxLength={key === 'title' ? 180 : 12000} disabled={busy || !editable || activeAnalysis} value={fields[key as keyof Fields]} onChange={event => { setFields({ ...fields, [key]: event.target.value }); setDirty(true) }} /></label>)}</div>
        {editable && <button disabled={busy || !dirty || activeAnalysis} onClick={save}>Save dossier</button>}
        <h3>Captured evidence</h3>{!dossier.evidence.length && <p>Capture graph resources or agent citations before submission.</p>}
        {dossier.evidence.map(item => <details key={item.id}><summary>{item.node.label} · {item.node.type}</summary>{editable && <button disabled={busy || dirty || activeAnalysis} onClick={() => run(() => changeRequest<Dossier>(`/${dossier.id}/evidence/remove`, { revision: dossier.revision, evidence_id: item.id }))}>Remove from draft dossier</button>}<p>Snapshot {item.snapshot_id} · captured {item.captured_at}</p><p>{item.relationship_count} incident relationships; {item.relationships_truncated ? 'bounded preview retained' : 'all retained'}.</p><button onClick={() => { setContextId(item.node.id); setTab('graph') }}>Highlight captured context</button><pre>{JSON.stringify({ resource: item.node, relationships: item.relationships, source_findings: item.source_findings, observations: item.observations }, null, 2)}</pre></details>)}
        {editable && <><p>{missing.length ? `Complete before submitting: ${missing.join(', ')}` : 'Required sections and evidence are present; review their accuracy before submission.'}</p>
          {dossier.automation_review_required && <label><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />I reviewed the agent-drafted dossier and its evidence.</label>}
          <button disabled={busy || dirty || activeAnalysis || !!missing.length || (dossier.automation_review_required && !acknowledged)} onClick={() => decide('submit')}>Submit for local review</button></>}
        {dossier.state === 'submitted' && <><label>Reviewer decision note<textarea maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /></label><div className="change-actions">{[['approve', 'Approve dossier'], ['request_changes', 'Request changes'], ['reject', 'Reject dossier']].map(([action, label]) => <button key={action} disabled={busy || !note.trim()} onClick={() => decide(action)}>{label}</button>)}</div></>}
        {!editable && <button disabled={busy} onClick={() => decide('revise')}>Create new draft revision</button>}
        <button disabled={busy || dossier.state !== 'approved'} onClick={exportDossier}>Download approved dossier</button>
        <button disabled title="External change-request creation is not configured">Submit externally</button><p>External change creation is not configured. Local approval and export do not mean an external ticket was created.</p>
        <details><summary>Version and decision history</summary>{dossier.versions.map(version => <details key={version.version}><summary>Submitted version {version.version} · {version.digest.slice(0, 12)}</summary>{!('turns' in version.dossier) && <p>Legacy version: historical conversation contents were not frozen and cannot be verified.</p>}<pre>{JSON.stringify(version.dossier, null, 2)}</pre></details>)}{dossier.audit.map((event, i) => <p key={i}>{event.at} · {event.action} · {event.note}</p>)}</details>
        <details onToggle={event => setAdvanced(event.currentTarget.open)}><summary>Advanced source / target / relationship actions</summary>
          {review?.result_digest === dossier.snapshot_digest && review.status === 'approved' && frozenGraph
            ? advanced && <CollaborationPanel review={review} graph={frozenGraph} catalog={catalog} selected={contextNode} />
            : <p>These existing ALM link actions require the matching active source review to be approved. Dossier approval is separate.</p>}</details>
      </>}
      {dossier && tab === 'graph' && <><p>Evidence graph for this dossier’s frozen snapshot. Select a resource to inspect it or capture it into the draft.</p><InteractiveGraph graph={frozenGraph} selected={contextId || null} onSelect={node => setContextId(node?.id || '')} busy={busy} highlighted={dossier.evidence.map(item => item.node.id)} active={active} />
        <button disabled={!contextId || busy || dirty || !editable || activeAnalysis} onClick={() => capture(contextId)}>Capture selected resource</button><button onClick={() => setTab('conversation')}>Discuss this context</button></>}
      {dossier && tab === 'table' && <><GraphDataTable graph={frozenGraph} resources={frozenGraph?.nodes || []} onSelect={node => setContextId(node.id)} /><button disabled={!contextId || busy || dirty || !editable || activeAnalysis} onClick={() => capture(contextId)}>Capture selected resource</button><p>Selected: {contextNode?.label || 'none'}</p></>}
      </Suspense>
    </div></div>
  </section>
}
