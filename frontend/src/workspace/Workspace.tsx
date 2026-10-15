import { useEffect, useMemo, useState } from 'react'
import { Activity, ArrowUpRight, Boxes, CheckCircle2, CircleDot, GitBranch, Network, Search, Settings2, ShieldCheck, Sparkles, Workflow, FileCode2, AlertCircle, X, Link2 } from 'lucide-react'
import { IxApplication, IxApplicationHeader, IxMenu, IxMenuItem, IxMenuCategory, IxContent, IxButton, IxSelect, IxSelectItem, IxAvatar } from '@siemens/ix-react'
import { iconGraph, iconTable, iconHistory, iconCheck, iconUserSettings, iconCode, iconRefresh, iconNetworkDevice } from '@siemens/ix-icons/icons'
import { requestJson, ReviewRecord, workspaceRequest, useReviewSession } from '../reviewSession'
import { Catalog, domainColors, domainOf, TraceGraph, TraceNode } from './types'
import InteractiveGraph from './InteractiveGraph'
import Companion from './Companion'
import SessionBar from '../components/SessionBar'
import ReviewPanel from '../components/ReviewPanel'
import AnalysisPage from '../components/AnalysisPage'
import QualityPage from '../components/QualityPage'
import SecurityPage from '../components/SecurityPage'
import './workspace.css'
import './siemens-ui.css'

type View = 'graph' | 'resources' | 'activity' | 'review' | 'connections' | 'analysis' | 'quality' | 'security'
export default function Workspace() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [source, setSource] = useState('')
  const [review, setReview] = useState<ReviewRecord | null>(null)
  const [view, setView] = useState<View>('graph')
  const [selected, setSelected] = useState<TraceNode | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [resourceQuery, setResourceQuery] = useState('')
  const [resourceDomain, setResourceDomain] = useState('ALL')
  const session = useReviewSession()
  const graph = (review?.result || null) as TraceGraph | null
  useEffect(() => {
    const clearExpired = () => {
      if (review && (!session || review.sessionToken !== session.token || Math.min(session.deadline, session.absoluteDeadline) <= Date.now())) {
        setReview(null); setSelected(null)
      }
    }
    clearExpired()
    const timer = setInterval(clearExpired, 1000)
    return () => clearInterval(timer)
  }, [review, session])
  useEffect(() => {
    requestJson('/api/v1/workspace/catalog').then(data => { setCatalog(data); setSource(data.sources[0]?.id || '') })
      .catch(cause => setError(cause instanceof Error ? cause.message : 'Central catalog unavailable'))
  }, [])
  const sync = async () => {
    if (!catalog || !source) return
    setBusy(true); setError('')
    try {
      const record = await workspaceRequest<ReviewRecord>('sync', { request_id: crypto.randomUUID(), source_id: source,
        include_lifecycle: true }, catalog.settings.request_timeout_seconds)
      setReview(record); setSelected(null); setView('graph')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Workspace synchronization failed') }
    finally { setBusy(false) }
  }
  const domainCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    graph?.nodes.forEach(node => { const domain = domainOf(node); counts[domain] = (counts[domain] || 0) + 1 })
    return counts
  }, [graph])
  const resources = useMemo(() => graph?.nodes.filter(node => (resourceDomain === 'ALL' || domainOf(node) === resourceDomain) && `${node.label} ${node.type} ${domainOf(node)} ${node.properties.path || ''}`.toLowerCase().includes(resourceQuery.toLowerCase())).slice(0, 150) || [], [graph, resourceQuery, resourceDomain])
  const lifecycleCount = graph?.nodes.filter(node => domainOf(node) !== 'CODE').length || 0
  const lifecycleLinks = graph?.edges.filter(edge => edge.properties.origin === 'lifecycle_assertion').length || 0
  const connectors = graph?.metadata.connectors || []
  const sourceLabel = catalog?.sources.find(item => item.id === source)?.label || 'Managed workspace'
  const navigate = (target: View) => { setView(target); if (target === 'resources') setResourceDomain('ALL') }
  const nav = [
    { id: 'graph', label: 'Graph explorer', icon: iconGraph }, { id: 'resources', label: 'Resource index', icon: iconTable },
    { id: 'activity', label: 'Change & delivery', icon: iconHistory }, { id: 'review', label: 'Review center', icon: iconCheck },
  ] as const
  return <IxApplication className="ix-workspace">
    <IxApplicationHeader name="CodeTrace Intelligence" nameSuffix="Lifecycle workspace">
      <span slot="logo" className="ix-product-mark" aria-label="CodeTrace">CT</span>
      <span slot="secondary" className="ix-local-badge">Local evidence · {sourceLabel}</span>
      <IxButton variant="tertiary" icon={iconUserSettings} onClick={() => navigate('connections')}>Connections</IxButton>
      <IxAvatar initials="LR" aria-label="Local reviewer" />
    </IxApplicationHeader>
    <IxMenu pinned startExpanded enableToggleTheme aria-label="Workspace navigation">
      {nav.map(item => <IxMenuItem key={item.id} icon={item.icon} active={view === item.id} onClick={() => navigate(item.id)}>{item.label}</IxMenuItem>)}
      <IxMenuCategory label="Lifecycle domains" icon={iconNetworkDevice}>
        {[['AM', 'Architecture'], ['RM', 'Requirements'], ['CM', 'Change management'], ['QM', 'Quality management'], ['TRS', 'Tracked resources']].map(([id, label]) => <IxMenuItem key={id} active={view === 'resources' && resourceDomain === id} onClick={() => { navigate('resources'); setResourceDomain(id); setResourceQuery('') }}>{label} · {domainCounts[id] || 0}</IxMenuItem>)}
      </IxMenuCategory>
      <IxMenuCategory label="Source analysis" icon={iconCode}>
        <IxMenuItem active={view === 'analysis'} onClick={() => navigate('analysis')}>Local folder analysis</IxMenuItem>
        <IxMenuItem active={view === 'quality'} onClick={() => navigate('quality')}>Quality assessment</IxMenuItem>
        <IxMenuItem active={view === 'security'} onClick={() => navigate('security')}>Security patterns</IxMenuItem>
      </IxMenuCategory>
      <IxMenuItem slot="bottom" icon={iconUserSettings} active={view === 'connections'} onClick={() => navigate('connections')}>Central connections</IxMenuItem>
    </IxMenu>
    <IxContent className="workspace-main" id="main-content">
      <div className="workspace-session"><SessionBar /></div>
      <main className="workspace-content">
        <div className="workspace-title-row"><div><span className="eyebrow">CODE + LIFECYCLE INTELLIGENCE</span><h1>{view === 'connections' ? 'Connected by design.' : view === 'review' ? 'Confidence, with evidence.' : 'The connected view.'}</h1><p>Understand the system. Follow the evidence. Know what changes.</p></div>
          <div className="source-actions"><IxSelect aria-label="Managed source" value={source} disabled={busy} onValueChange={event => { setSource(String(event.detail)); setReview(null); setSelected(null) }}>{catalog?.sources.map(item => <IxSelectItem key={item.id} value={item.id} label={item.label} />)}</IxSelect>
            <IxButton icon={iconRefresh} loading={busy} disabled={busy || !source} onClick={sync}>{busy ? 'Synchronizing' : 'Synchronize'}</IxButton></div>
        </div>
        {error && <div className="workspace-alert" role="alert"><AlertCircle size={16} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={14} /></button></div>}
        {graph && connectors.some((item: any) => item.status !== 'ready') && <div className="workspace-alert caution"><AlertCircle size={16} /><span>Some lifecycle connections are partial or unavailable. Review connection evidence before making impact claims.</span><button onClick={() => navigate('connections')}>View status</button></div>}
        {['graph', 'resources', 'activity', 'review'].includes(view) && <div className="metric-strip">
          <Metric label="SOURCE FILES" value={graph?.metadata.files || 0} note={graph ? sourceLabel : 'Awaiting synchronization'} icon={<FileCode2 size={17} />} />
          <Metric label="GRAPH RESOURCES" value={graph?.nodes.length || 0} note={`${domainCounts.CODE || 0} code · ${lifecycleCount} lifecycle`} icon={<Boxes size={17} />} />
          <Metric label="LIFECYCLE LINKS" value={lifecycleLinks} note={catalog?.providers.length ? 'Explicit provider assertions' : 'Configure OSLC providers to connect'} icon={<Link2 size={17} />} />
          <Metric label="REVIEW STATE" value={review?.status || 'Ready'} note={review ? `Snapshot · ${review.elapsed_seconds}s to index` : 'Every result starts pending'} icon={<ShieldCheck size={17} />} />
        </div>}
        {view === 'graph' && <div className="explorer-grid"><div className="explorer-left"><InteractiveGraph graph={graph} selected={selected?.id || null} onSelect={setSelected} busy={busy} />
          <div className="evidence-strip"><div><span className="live-dot" /><strong>{graph ? 'Evidence synchronized' : 'Source catalog ready'}</strong><span>{graph ? new Date(graph.metadata.indexed_at).toLocaleString() : 'Managed connections are configured centrally'}</span></div><button onClick={() => navigate('activity')}>Track changes<ArrowRightIcon /></button></div>
        </div><Companion graph={graph} review={review} selected={selected} catalog={catalog} onSelect={setSelected} /></div>}
        {view === 'resources' && <div className="explorer-grid"><section className="resource-panel"><div className="section-title"><div><span className="eyebrow">EVERY RESOURCE, IN CONTEXT</span><h2>Resource index</h2></div><div className="index-search"><Search size={14} /><input aria-label="Filter resource index" placeholder="Search type, domain, or source…" value={resourceQuery} onChange={event => setResourceQuery(event.target.value)} /></div></div>
          <div className="resource-table-wrap"><table className="resource-table"><thead><tr><th>Resource</th><th>Domain</th><th>Evidence</th><th /></tr></thead><tbody>{resources.map(node => <tr key={node.id} className={selected?.id === node.id ? 'selected' : ''} onClick={() => setSelected(node)}><td><button onClick={() => setSelected(node)}><i style={{ background: domainColors[domainOf(node)] || '#aaa' }} /><strong>{node.label}</strong><small>{node.type.replace(/_/g, ' ')}</small></button></td><td><span className="domain-tag">{domainOf(node)}</span></td><td className="resource-path">{node.properties.path || node.properties.provider_id || 'Graph provenance'}</td><td><ArrowUpRight size={13} /></td></tr>)}</tbody></table>
            {!resources.length && <div className="empty-section">{graph ? 'No resources match this filter.' : 'Synchronize a managed source to inspect its resource index.'}</div>}</div><div className="table-footer">Showing {resources.length} of {graph?.nodes.length || 0} resources. Search narrows the indexed graph.</div></section><Companion graph={graph} review={review} selected={selected} catalog={catalog} onSelect={setSelected} /></div>}
        {view === 'activity' && <div className="activity-grid"><section className="plain-panel"><div className="section-title"><div><span className="eyebrow">TRACKED RESOURCE SET</span><h2>Lifecycle change feed</h2></div><Activity size={20} /></div>
          {graph?.trs_events?.length ? [...graph.trs_events].reverse().map(event => <div className="timeline-event" key={event.id}><div className={'event-dot ' + event.action.toLowerCase()} /><div><span className="event-label">{event.action} <small>#{event.order}</small></span><button onClick={() => { const node = graph.nodes.find(item => item.id === event.resource_uri); if (node) { setSelected(node); setView('resources') } }}>{graph.nodes.find(item => item.id === event.resource_uri)?.label || event.resource_uri}</button><p>{event.provider_id} · {event.at ? new Date(event.at).toLocaleString() : 'Time not supplied by provider'}</p></div></div>) : <div className="empty-section"><Activity size={25} /><h3>No imported TRS events yet.</h3><p>Configure a TRS endpoint or RDF export centrally. Change order, checkpoints, and deletion tombstones appear here after sync.</p></div>}
          <div className="checkpoint-list">{connectors.filter((item: any) => item.domain === 'TRS').map((item: any) => <div key={item.id}><strong>{item.label}</strong><span>Checkpoint {item.checkpoint?.latest_order ?? 'unavailable'} · {item.status}</span></div>)}</div></section>
          <section className="plain-panel"><div className="section-title"><div><span className="eyebrow">CONTINUOUS DELIVERY</span><h2>Build evidence</h2></div><Workflow size={20} /></div>{graph?.pipeline_runs?.length ? graph.pipeline_runs.map(run => <div className="pipeline-run" key={run.id}><CheckCircle2 size={18} /><div><strong>{run.label}</strong><p>{run.branch} · {run.revision?.slice(0, 8)}</p></div><span className={'pipeline-status ' + (run.matches_revision ? 'matched' : '')}>{run.status}</span><small>{run.matches_revision ? 'Matches indexed revision' : 'Different revision'}</small></div>) : <div className="empty-section"><Workflow size={25} /><h3>Bring delivery into the picture.</h3><p>Add GitHub Actions or GitLab CI connections to the central catalog. Build status is linked only when its revision matches the source.</p></div>}</section></div>}
        {view === 'review' && <section className="review-center"><div className="section-title"><div><span className="eyebrow">REVIEW WITH PROVENANCE</span><h2>Snapshot decision</h2></div><ShieldCheck size={22} /></div>{review ? <><div className="review-summary"><CircleDot size={18} /><div><strong>{graph?.metadata.source_label}</strong><p>{graph?.nodes.length} resources · {graph?.edges.length} relationships · revision {String(graph?.metadata.revision || 'unversioned').slice(0, 12)}</p></div><span className={'status-pill ' + review.status}>{review.status}</span></div><ReviewPanel key={review.id} review={review} onChange={setReview} /><div className="review-caveat">Review covers this snapshot. Provider gaps and static-analysis limitations remain visible in its evidence.</div></> : <div className="empty-section">Synchronize a managed source to create a reviewable graph snapshot.</div>}</section>}
        {view === 'connections' && <Connections catalog={catalog} connectors={connectors} />}
        {view === 'analysis' && <AnalysisPage onBack={() => navigate('graph')} onNavigateToGraph={() => navigate('graph')} onNavigateToQuality={() => navigate('quality')} />}
        {view === 'quality' && <QualityPage onBack={() => navigate('graph')} />}
        {view === 'security' && <SecurityPage />}
        <footer className="workspace-footer"><span>CODETRACE INTELLIGENCE WORKSPACE</span><span>OSLC contextual evidence · local reviewer decisions · session bounded</span><button onClick={() => navigate('connections')}><Settings2 size={12} />Central administration</button></footer>
      </main>
    </IxContent>
  </IxApplication>
}

function ArrowRightIcon() { return <ArrowUpRight size={13} /> }
function Metric({ label, value, note, icon }: { label: string; value: number | string; note: string; icon: React.ReactNode }) {
  return <div className="metric-card"><div><span>{label}</span>{icon}</div><strong>{typeof value === 'number' ? value.toLocaleString() : value}</strong><small>{note}</small></div>
}
function Connections({ catalog, connectors }: { catalog: Catalog | null; connectors: any[] }) {
  return <section className="connections-panel"><div className="connection-intro"><div><span className="eyebrow">ONE CENTRAL CATALOG</span><h2>Administration belongs in configuration.</h2><p>Repository locations, lifecycle providers, pipelines, credentials and AI settings are managed through the root <code>.env.local</code>. Users choose sources; connection secrets stay on the server.</p></div><Settings2 size={38} /></div>
    <div className="connection-grid"><ConnectionCard title="Managed repositories" subtitle="MANAGED_REPOSITORIES" icon={<GitBranch size={19} />}>
      {catalog?.sources.map(source => <div className="connection-row" key={source.id}><span><strong>{source.label}</strong><small>{source.kind} · {source.ref || 'Working revision'}</small></span><b>Configured</b></div>)}
    </ConnectionCard><ConnectionCard title="OSLC lifecycle providers" subtitle="OSLC_PROVIDERS" icon={<Network size={19} />}>
      {catalog?.providers.length ? catalog.providers.map(provider => <div className="connection-row" key={provider.id}><span><strong>{provider.label}</strong><small>{provider.domain} · {provider.transport}</small></span><b>{connectors.find(item => item.id === provider.id)?.status || 'Configured'}</b></div>) : <p className="connection-empty">No provider configured. Add AM, RM, CM, TRS, QM or ResourceShape data through managed endpoints or RDF files.</p>}
    </ConnectionCard><ConnectionCard title="Delivery connections" subtitle="CI_PROVIDERS" icon={<Workflow size={19} />}>
      {catalog?.pipelines.length ? catalog.pipelines.map(provider => <div className="connection-row" key={provider.id}><span><strong>{provider.label}</strong><small>{provider.platform}</small></span><b>{connectors.find(item => item.id === provider.id)?.status || 'Configured'}</b></div>) : <p className="connection-empty">No CI connection configured. GitHub Actions and GitLab pipeline adapters are available.</p>}
    </ConnectionCard><ConnectionCard title="Local AI companion" subtitle="AI_PROVIDER · AI_MODEL" icon={<Sparkles size={19} />}>
      <div className="connection-row"><span><strong>{catalog?.ai.provider || 'Loading'}</strong><small>{catalog?.ai.model || 'No model configured'}</small></span><b>Configured</b></div><p className="connection-empty">Inference availability is checked when asking a question. Graph evidence remains available if the model is offline.</p>
    </ConnectionCard></div>
    <div className="connection-guidance"><ShieldCheck size={17} /><div><strong>Configuration is server managed.</strong><p>Use JSON arrays for catalogs. Provider tokens are referenced by environment-variable name. Restart services after changing settings. This local app does not provide account-based administrative access.</p></div></div>
  </section>
}
function ConnectionCard({ title, subtitle, icon, children }: { title: string; subtitle: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="connection-card"><div className="connection-card-heading">{icon}<h3>{title}</h3></div><code>{subtitle}</code>{children}</div>
}
