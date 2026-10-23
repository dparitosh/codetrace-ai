import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight, ArrowRight, ChevronRight, Code2, Sparkles, X, FileText, Link2 } from 'lucide-react'
import { aiRequest, ReviewRecord, workspaceRequest } from '../reviewSession'
import type { AIProfile } from './AISettings'
import { Catalog, CompanionAnswer, domainColors, domainOf, relationLabel, TraceGraph, TraceNode } from './types'
import NodeBadge from './NodeBadge'

interface Props { graph: TraceGraph | null; review: ReviewRecord | null; selected: TraceNode | null; catalog: Catalog | null; onSelect: (node: TraceNode) => void; onHighlight?: (ids: string[]) => void; contextDomain?: string; onStartChange?: () => void }
export default function Companion({ graph, review, selected, catalog, onSelect, onHighlight, contextDomain = 'ALL', onStartChange }: Props) {
  const [tab, setTab] = useState<'ask' | 'inspect'>('ask')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<CompanionAnswer | null>(null)
  const [answerDomain, setAnswerDomain] = useState('ALL')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState<AIProfile | null>(null)
  const [agentId, setAgentId] = useState('trace-explorer')
  useEffect(() => {
    let active = true
    const load = () => { if (review) aiRequest<AIProfile>('config').then(value => { if (active) setProfile(value) }).catch(() => { if (active) setProfile(null) }) }
    load(); window.addEventListener('codetrace:ai-config', load)
    return () => { active = false; window.removeEventListener('codetrace:ai-config', load) }
  }, [review])
  const requestGeneration = useRef(0)
  const [edgeLimit, setEdgeLimit] = useState(12)
  useEffect(() => setEdgeLimit(12), [selected?.id, graph])
  useEffect(() => {
    const invalidate = () => { requestGeneration.current++ }
    invalidate(); setAnswer(null); setError(''); setBusy(false)
    return invalidate
  }, [review?.id, review?.sessionToken])
  useEffect(() => { requestGeneration.current++; setBusy(false); setError('') }, [contextDomain])
  useEffect(() => { if (selected) setTab('inspect') }, [selected])
  const ask = async (value: string) => {
    if (!review || !value.trim() || !catalog || busy) return
    const generation = ++requestGeneration.current
    const chosenAgent = agentId === 'trace-explorer' && /gap|coverage|traceability/i.test(value) ? 'coverage-reviewer'
      : agentId === 'trace-explorer' && /similar|impact|build|change/i.test(value) ? 'change-analyst' : agentId
    setAgentId(chosenAgent)
    setTab('ask'); setBusy(true); setError(''); setQuestion(value)
    try {
      const result = await workspaceRequest<CompanionAnswer>('agent/run', { review_id: review.id, question: value,
        selected_id: selected?.id, agent_id: chosenAgent, domain: contextDomain }, profile?.request_timeout_seconds || catalog.ai.timeout_seconds + 5, review.sessionToken)
      if (generation !== requestGeneration.current) return
      setAnswer(result)
      setAnswerDomain(contextDomain)
      onHighlight?.(result.highlight_ids || [])
      setQuestion('')
    } catch (cause) { if (generation === requestGeneration.current) setError(cause instanceof Error ? cause.message : 'Companion request failed') }
    finally { if (generation === requestGeneration.current) setBusy(false) }
  }
  const edges = graph && selected ? graph.edges.filter(edge => edge.source === selected.id || edge.target === selected.id) : []
  const nodes = useMemo(() => new Map(graph?.nodes.map(node => [node.id, node]) || []), [graph])
  const prompts = ['Where are the traceability gaps?', 'Explain the selected resource', 'Find similar resources to the selected resource', 'Which builds match this revision?']
  return <aside className="companion-panel">
    {onStartChange && <button disabled={!review} onClick={onStartChange}>Open change conversation & dossier</button>}
    <div className="companion-heading"><div className="companion-icon"><Sparkles size={19} /></div><div><h2>Companion</h2></div><small>{contextDomain === 'ALL' ? 'All domains' : contextDomain}</small></div>
    <div className="companion-tabs"><button className={tab === 'ask' ? 'active' : ''} onClick={() => setTab('ask')}><Sparkles size={13} />Ask companion</button><button className={tab === 'inspect' ? 'active' : ''} onClick={() => setTab('inspect')}><Code2 size={13} />Inspect resource</button></div>
    <label className="agent-selector">Agent<select aria-label="Graph agent" value={agentId} disabled={busy} onChange={event => setAgentId(event.target.value)}>{(profile?.agents || [{ id: 'trace-explorer', label: 'Trace explorer' }]).map(agent => <option key={agent.id} value={agent.id}>{agent.label}</option>)}</select></label>
    <div className="companion-content">
      {tab === 'ask' ? <>
        {!answer && <div className="companion-intro"><p>Ask a question or start with a graph query.</p>
          <div className="companion-prompts">{prompts.map(prompt => <button key={prompt} disabled={!review || busy} onClick={() => ask(prompt)}>{prompt}<ArrowUpRight size={14} /></button>)}</div></div>}
        {answer && <div className="companion-answer"><div className="answer-label"><Sparkles size={13} />{answer.mode === 'evidence' ? 'GRAPH EVIDENCE' : 'AGENT ANSWER'} · {answerDomain}<button aria-label="Clear companion answer" onClick={() => setAnswer(null)}><X size={13} /></button></div>
          <p className="answer-body">{answer.answer}</p>
          {answer.trace && <details className="agent-execution"><summary>Agent execution · {answer.trace.length} tools</summary>{answer.trace.map(step => <div key={step.step}><strong>{step.step}. {step.tool.replace(/_/g, ' ')}</strong><small>{step.status} · {step.resource_ids.length} resources · {step.elapsed_ms} ms</small><button onClick={() => onHighlight?.(step.resource_ids)}>Highlight step evidence</button><details><summary>Parameters</summary><pre>{JSON.stringify(step.arguments, null, 2)}</pre></details></div>)}</details>}
          {answer.warning && <p className="answer-warning">{answer.warning}</p>}
          <div className="evidence-heading"><Link2 size={12} />CITED RESOURCES</div>
          <div className="citation-list">{answer.citations.map(citation => <button key={citation.citation_id} onClick={() => { const node = nodes.get(citation.node_id); if (node) onSelect(node) }}><b>{citation.citation_id}</b><span>{citation.label}<small>{citation.domain} · {citation.type.replace(/_/g, ' ')}</small></span><ChevronRight size={13} /></button>)}</div>
          {!!answer.similar_resources?.length && <><div className="evidence-heading">SIMILAR RESOURCES · FEATURE OVERLAP</div><div className="citation-list">{answer.similar_resources.map(item => <button key={item.node_id} onClick={() => { const node = nodes.get(item.node_id); if (node) onSelect(node) }}><span>{item.label}<small>Label {Math.round(item.lexical_overlap * 100)}% · structure {Math.round(item.structural_overlap * 100)}%</small></span></button>)}</div><p className="answer-warning">Overlap is a retrieval signal, not semantic equivalence or a safe substitution.</p></>}
          {answer.recommendations?.map((item, index) => <p className="answer-warning" key={index}>{item.message} {item.basis}</p>)}
        </div>}
        {busy && <div className="companion-thinking"><span className="pulse-dot" />Executing bounded graph tools and verifying evidence…</div>}
      </> : selected ? <div className="resource-inspector">
        <h3>{selected.label}</h3><NodeBadge node={selected} />
        <dl><dt>Evidence origin</dt><dd>{String(selected.properties.origin || 'Code analyzer').replace(/_/g, ' ')}</dd>
          {selected.properties.path && <><dt>Source location</dt><dd className="source-location"><FileText size={12} />{selected.properties.path}{selected.properties.start ? ':' + selected.properties.start : ''}</dd></>}
          {selected.properties.status && <><dt>Status</dt><dd>{selected.properties.status}</dd></>}
          {selected.properties.outcome && <><dt>Provider test outcome</dt><dd>{selected.properties.outcome}</dd></>}
          {selected.properties.provider_id && <><dt>Provider</dt><dd>{selected.properties.provider_id}</dd></>}
          {selected.properties.resource_shape && <><dt>Resource shape</dt><dd>{selected.properties.resource_shape}</dd></>}
          {selected.properties.deleted && <><dt>TRS state</dt><dd className="deleted-state">Deleted resource · tombstone retained</dd></>}
        </dl>
        <button className="inspect-ask" disabled={busy} onClick={() => ask('Explain this resource and its trace links. Identify any missing evidence.')}><Sparkles size={14} />Explain this context<ArrowRight size={14} /></button>
        <h4>Relationships <span>{edges.length}</span></h4>
        <p>{new Set(edges.map(edge => edge.source === selected?.id ? edge.target : edge.source)).size} connected resources · showing {Math.min(edgeLimit, edges.length)} of {edges.length} relationships</p>
        <div className="connected-list">{edges.length ? edges.slice(0, edgeLimit).map((edge, index) => {
          const target = nodes.get(edge.source === selected.id ? edge.target : edge.source)
          return target && <button key={index} onClick={() => onSelect(target)}><span className="relationship-direction">{edge.source === selected.id ? 'OUT' : 'IN'}</span><span>{target.label}<small>{relationLabel(edge.type)}</small></span><ChevronRight size={12} /></button>
        }) : <p>No explicit relationships found.</p>}</div>
        {edges.length > edgeLimit && <button onClick={() => setEdgeLimit(current => current + 12)}>Show more relationships</button>}
        <details className="resource-identity"><summary>Resource identity & provenance</summary><code>{selected.id}</code><pre>{JSON.stringify(selected.properties, null, 2)}</pre></details>
      </div> : <div className="inspector-empty"><Code2 size={28} /><h3>Every node has a story.</h3><p>Select a graph resource or use the resource index to inspect its source, schema, and relationships.</p></div>}
      {error && <p className="companion-error" role="alert">{error}</p>}
    </div>
    <form className="companion-compose" onSubmit={event => { event.preventDefault(); ask(question) }}>
      {selected && <div className="context-pill"><i style={{ background: domainColors[domainOf(selected)] }} />Context: {selected.label}</div>}
      <div><textarea aria-label="Ask trace companion" placeholder={review ? 'Ask about impact, coverage, or a resource…' : 'Synchronize a source to start exploring…'} maxLength={1500} value={question} onChange={event => setQuestion(event.target.value)} disabled={!review || busy} /><button aria-label="Send companion question" disabled={!review || busy || !question.trim()}><ArrowUpRight size={17} /></button></div>
      <p><span className="local-indicator" />{profile?.enabled ? `Ollama · ${profile.model || 'select a model'} · evidence cited` : 'Graph tools · model planning disabled'}</p>
    </form>
  </aside>
}
