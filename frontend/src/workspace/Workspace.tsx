import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Activity, CheckCircle2, CircleDot, GitBranch, Network, Search, Settings2, ShieldCheck, Sparkles, Workflow, AlertCircle, X } from 'lucide-react'
import { IxApplication, IxApplicationHeader, IxMenu, IxMenuItem, IxMenuCategory, IxContent, IxButton, IxSelect, IxSelectItem, IxAvatar } from '@siemens/ix-react'
import { iconGraph, iconTable, iconHistory, iconCheck, iconUserSettings, iconCode, iconRefresh, iconNetworkDevice } from '@siemens/ix-icons/icons'
import { requestJson, ReviewRecord, workspaceRequest, useReviewSession, submitForReview, subscribeReviewChanges } from '../reviewSession'
import { loadSourceConfiguration, readSourceFiles } from '../sourceFiles'
import { WorkspaceGraphContext, mergeSnapshotReview } from './workspaceContext'
import { Catalog, domainOf, TraceGraph, TraceNode } from './types'
const InteractiveGraph = lazy(() => import('./InteractiveGraph'))
import { matchingNodes } from './graphModel'
const Companion = lazy(() => import('./Companion'))
const CollaborationPanel = lazy(() => import('./CollaborationPanel'))
const AdminModule = lazy(() => import('./AdminModule'))
const GraphDataTable = lazy(() => import('./GraphDataTable'))
const ContextualSearch = lazy(() => import('./ContextualSearch'))
const DomainOverview = lazy(() => import('./DomainOverview'))
import EvidenceTabs from './EvidenceTabs'
import SessionBar from '../components/SessionBar'
const ReviewPanel = lazy(() => import('../components/ReviewPanel'))
const AnalysisPage = lazy(() => import('../components/AnalysisPage'))
const QualityPage = lazy(() => import('../components/QualityPage'))
const SecurityPage = lazy(() => import('../components/SecurityPage'))
import './workspace.css'
import './siemens-ui.css'
import './graphContext.css'

type View = 'graph' | 'resources' | 'activity' | 'review' | 'connections' | 'admin' | 'analysis' | 'quality' | 'security'
export default function Workspace() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [source, setSource] = useState('')
  const [review, setReview] = useState<ReviewRecord | null>(null)
  const [view, setView] = useState<View>('graph')
  const [selected, setSelected] = useState<TraceNode | null>(null)
  const [highlighted, setHighlighted] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [resourceQuery, setResourceQuery] = useState('')
  const [resourceDomain, setResourceDomain] = useState('ALL')
  const [explorerMode, setExplorerMode] = useState<'overview' | 'graph' | 'table'>('graph')
  const [companionOpen, setCompanionOpen] = useState(false)
  const [tableActivated, setTableActivated] = useState(false)
  useEffect(() => { if (explorerMode === 'table') setTableActivated(true) }, [explorerMode])
  const [uploadLabel, setUploadLabel] = useState('')
  const [notice, setNotice] = useState('')
  const session = useReviewSession()
  const graph = (review?.result || null) as TraceGraph | null
  const updateReview = (record: ReviewRecord) => setReview(current => mergeSnapshotReview(current, record))
  useEffect(() => subscribeReviewChanges(record => setReview(current =>
    current?.id === record.id && current.sessionToken === record.sessionToken ? mergeSnapshotReview(current, record) : current)), [])
  useEffect(() => setHighlighted([]), [graph])
  useEffect(() => {
    const clearExpired = () => {
      if (review && (!session || review.sessionToken !== session.token || Math.min(session.deadline, session.absoluteDeadline) <= Date.now())) {
        setReview(null); setSelected(null); setUploadLabel(''); setNotice('')
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
      setReview(record); setSelected(null); setUploadLabel(''); setNotice('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Workspace synchronization failed') }
    finally { setBusy(false) }
  }
  const analyzeUpload = async (files: File[]) => {
    if (!files.length || busy) return false
    setBusy(true); setError(''); setNotice('')
    try {
      const config = await loadSourceConfiguration()
      const sourceFiles = await readSourceFiles(files, setNotice, config)
      const record = await submitForReview('graph', { files: sourceFiles }, config.request_timeout_seconds)
      setReview(record); setSelected(null); setResourceDomain('CODE'); setExplorerMode('overview')
      setUploadLabel(files[0].webkitRelativePath?.split('/')[0] || 'Uploaded source folder')
      return true
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Folder analysis failed'); return false }
    finally { setBusy(false) }
  }
  const domainCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    graph?.nodes.forEach(node => { const domain = domainOf(node); counts[domain] = (counts[domain] || 0) + 1 })
    return counts
  }, [graph])
  const filteredResources = useMemo(() => (resourceQuery.trim() ? matchingNodes(graph, resourceQuery, Infinity) : graph?.nodes || []).filter(node => resourceDomain === 'ALL' || domainOf(node) === resourceDomain), [graph, resourceQuery, resourceDomain])
  const connectors = graph?.metadata.connectors || []
  const sourceLabel = uploadLabel || catalog?.sources.find(item => item.id === source)?.label || 'Managed workspace'
  const changeDomain = (domain: string) => {
    setResourceDomain(domain)
    setSelected(current => domain === 'ALL' || !current || domainOf(current) === domain ? current : null)
  }
  const explorerActive = ['graph', 'resources', 'analysis', 'quality', 'security'].includes(view)
  const hasOverview = ['analysis', 'quality', 'security'].includes(view) || (view === 'resources' && resourceDomain !== 'ALL')
  const selectResource = (node: TraceNode | null) => { setSelected(node); if (node) setCompanionOpen(true) }
  const heading = view === 'analysis' ? 'Source analysis' : view === 'quality' ? 'Quality assessment'
    : view === 'security' ? 'Security patterns' : view === 'resources' ? (resourceDomain === 'ALL' ? 'Resource index' : `${resourceDomain} lifecycle context`)
      : view === 'review' ? 'Review center' : view === 'connections' ? 'Connections' : view === 'admin' ? 'Administration'
        : view === 'activity' ? 'Change & delivery' : 'Graph explorer'
  const navigate = (target: View) => {
    setView(target)
    if (target === 'resources' || target === 'graph') changeDomain('ALL')
    setCompanionOpen(false)
    if (target === 'graph') setExplorerMode('graph')
    if (['analysis', 'quality', 'security'].includes(target)) { changeDomain('CODE'); setExplorerMode('overview') }
    if (target === 'resources') setExplorerMode('table')
  }
  const nav = [
    { id: 'graph', label: 'Graph explorer', icon: iconGraph }, { id: 'resources', label: 'Resource index', icon: iconTable },
    { id: 'activity', label: 'Change & delivery', icon: iconHistory }, { id: 'review', label: 'Review center', icon: iconCheck },
  ] as const
  return <WorkspaceGraphContext.Provider value={{ graph, review, sourceLabel, busy, uploaded: !!uploadLabel, notice,
    synchronize: sync, analyzeUpload, select: selectResource, openGraph: () => setExplorerMode('graph') }}><IxApplication className="ix-workspace">
    <IxApplicationHeader name="CodeTrace Intelligence" nameSuffix="Lifecycle workspace">
      <span slot="logo" className="ix-product-mark" aria-label="CodeTrace">CT</span>
      <IxButton variant="tertiary" icon={iconUserSettings} onClick={() => navigate('connections')}>Connections</IxButton>
      <IxAvatar initials="LR" aria-label="Local reviewer" />
    </IxApplicationHeader>
    <IxMenu pinned startExpanded enableToggleTheme aria-label="Workspace navigation">
      {nav.map(item => <IxMenuItem key={item.id} icon={item.icon} active={view === item.id && (item.id !== 'resources' || resourceDomain === 'ALL')} onClick={() => navigate(item.id)}>{item.label}</IxMenuItem>)}
      <IxMenuCategory label="Lifecycle domains" icon={iconNetworkDevice}>
        {[['AM', 'Architecture'], ['RM', 'Requirements'], ['CM', 'Change management'], ['QM', 'Quality management'], ['TRS', 'Tracked resources']].map(([id, label]) => <IxMenuItem key={id} active={view === 'resources' && resourceDomain === id} onClick={() => { navigate('resources'); changeDomain(id); setResourceQuery(''); setExplorerMode('overview') }}>{label} · {domainCounts[id] || 0}</IxMenuItem>)}
      </IxMenuCategory>
      <IxMenuCategory label="Source analysis" icon={iconCode}>
        <IxMenuItem active={view === 'analysis'} onClick={() => navigate('analysis')}>Source overview</IxMenuItem>
        <IxMenuItem active={view === 'quality'} onClick={() => navigate('quality')}>Quality assessment</IxMenuItem>
        <IxMenuItem active={view === 'security'} onClick={() => navigate('security')}>Security patterns</IxMenuItem>
      </IxMenuCategory>
      <IxMenuItem slot="bottom" icon={iconUserSettings} active={view === 'admin'} onClick={() => navigate('admin')}>Administration</IxMenuItem>
    </IxMenu>
    <IxContent className="workspace-main" id="main-content">
      <div className="workspace-session"><SessionBar /></div>
      <main className="workspace-content">
        <div className="workspace-title-row"><h1>{heading}</h1>
          {!['admin', 'connections'].includes(view) && <div className="source-actions"><IxSelect aria-label="Managed source" value={source} disabled={busy} onValueChange={event => { setSource(String(event.detail)); setReview(null); setSelected(null); setUploadLabel(''); setNotice('') }}>{catalog?.sources.map(item => <IxSelectItem key={item.id} value={item.id} label={item.label} />)}</IxSelect>
            <IxButton icon={iconRefresh} loading={busy} disabled={busy || !source} onClick={sync}>{busy ? 'Synchronizing' : 'Synchronize'}</IxButton></div>}
        </div>
        {!['admin', 'connections'].includes(view) && <div className="workspace-snapshot" aria-label="Active snapshot"><span>{sourceLabel}</span><span>{review ? `Snapshot ${String(graph?.metadata.snapshot_id || review.result_digest).slice(0, 8)}` : 'Not synchronized'}</span>{review && <span className={'snapshot-status ' + review.status}>{review.status}</span>}</div>}
        {error && <div className="workspace-alert" role="alert"><AlertCircle size={16} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={14} /></button></div>}
        {graph && connectors.some((item: any) => item.status !== 'ready') && <div className="workspace-alert caution"><AlertCircle size={16} /><span>Some lifecycle connections are partial or unavailable. Review connection evidence before making impact claims.</span><button onClick={() => navigate('connections')}>View status</button></div>}
        <Suspense fallback={<p role="status">Loading workspace tools...</p>}>
        <div className={'explorer-grid' + (!companionOpen ? ' companion-closed' : '')} style={{ display: explorerActive ? undefined : 'none' }}><div className="explorer-left">
          <div className="evidence-tab-row"><EvidenceTabs value={explorerMode} onChange={setExplorerMode} overview={hasOverview ? view === 'security' ? 'Findings' : view === 'quality' ? 'Assessment' : 'Overview' : undefined} /><IxButton variant="tertiary" aria-pressed={companionOpen} onClick={() => setCompanionOpen(value => !value)}>{companionOpen ? 'Hide companion' : 'Agent & inspector'}</IxButton></div>
          {explorerMode === 'overview' && <div role="tabpanel" id="evidence-overview-panel" aria-labelledby="evidence-overview-tab">{view === 'analysis' && <AnalysisPage />}{view === 'quality' && <QualityPage />}{view === 'security' && <SecurityPage />}{view === 'resources' && <DomainOverview graph={graph} domain={resourceDomain} onSelect={selectResource} onConnections={() => navigate('connections')} />}</div>}
          {explorerMode !== 'overview' && graph && resourceDomain !== 'ALL' && !domainCounts[resourceDomain] && <div className="workspace-alert caution"><span>No {resourceDomain} resources imported.</span><button onClick={() => navigate('connections')}>Configure connections</button></div>}
          <div role="tabpanel" id="evidence-graph-panel" aria-labelledby="evidence-graph-tab" hidden={explorerMode !== 'graph'}>
            <details className="description-search"><summary>Search by description</summary><ContextualSearch review={review} graph={graph} onSelect={selectResource} onHighlight={setHighlighted} domain={resourceDomain} /></details>
            <InteractiveGraph graph={graph} selected={selected?.id || null} onSelect={selectResource} busy={busy} highlighted={highlighted} active={explorerActive && explorerMode === 'graph'} domainFilter={resourceDomain} onDomainChange={changeDomain} /></div>
          {(tableActivated || explorerMode === 'table') && <section className="resource-panel" role="tabpanel" id="evidence-table-panel" aria-labelledby="evidence-table-tab" hidden={explorerMode !== 'table'}><div className="data-grid-toolbar"><span>{resourceDomain === 'ALL' ? 'All domains' : resourceDomain}</span><div className="index-search"><Search size={14} /><input aria-label="Filter resource index" placeholder="Filter resources…" value={resourceQuery} onChange={event => setResourceQuery(event.target.value)} /></div></div>
            <GraphDataTable graph={graph} resources={filteredResources} onSelect={selectResource} /></section>}
        </div><div hidden={!companionOpen}><Companion graph={graph} review={review} selected={selected} catalog={catalog} onSelect={selectResource} onHighlight={setHighlighted} contextDomain={resourceDomain} /></div></div>
        {view === 'activity' && <div className="activity-grid"><section className="plain-panel"><div className="section-title"><div><h2>Lifecycle change feed</h2></div><Activity size={20} /></div>
          {graph?.trs_events?.length ? [...graph.trs_events].reverse().map(event => <div className="timeline-event" key={event.id}><div className={'event-dot ' + event.action.toLowerCase()} /><div><span className="event-label">{event.action} <small>#{event.order}</small></span><button onClick={() => { const node = graph.nodes.find(item => item.id === event.resource_uri); if (node) { selectResource(node); changeDomain('ALL'); setExplorerMode('table'); setView('resources') } }}>{graph.nodes.find(item => item.id === event.resource_uri)?.label || event.resource_uri}</button><p>{event.provider_id} · {event.at ? new Date(event.at).toLocaleString() : 'Time not supplied by provider'}</p></div></div>) : <div className="empty-section"><Activity size={25} /><h3>No imported TRS events yet.</h3><p>Configure a TRS endpoint or RDF export centrally. Change order, checkpoints, and deletion tombstones appear here after sync.</p></div>}
          <div className="checkpoint-list">{connectors.filter((item: any) => item.domain === 'TRS').map((item: any) => <div key={item.id}><strong>{item.label}</strong><span>Checkpoint {item.checkpoint?.latest_order ?? 'unavailable'} · {item.status}</span></div>)}</div></section>
          <section className="plain-panel"><div className="section-title"><div><h2>Build evidence</h2></div><Workflow size={20} /></div>{graph?.pipeline_runs?.length ? graph.pipeline_runs.map(run => <div className="pipeline-run" key={run.id}><CheckCircle2 size={18} /><div><strong>{run.label}</strong><p>{run.branch} · {run.revision?.slice(0, 8)}</p></div><span className={'pipeline-status ' + (run.matches_revision ? 'matched' : '')}>{run.status}</span><small>{run.matches_revision ? 'Matches indexed revision' : 'Different revision'}</small></div>) : <div className="empty-section"><Workflow size={25} /><h3>No build evidence imported</h3><p>Add GitHub Actions or GitLab CI connections to the central catalog. Build status is linked only when its revision matches the source.</p></div>}</section></div>}
        {view === 'review' && <section className="review-center"><div className="section-title"><div><h2>Snapshot decision</h2></div><ShieldCheck size={22} /></div>{review ? <><div className="review-summary"><CircleDot size={18} /><div><strong>{graph?.metadata.source_label}</strong><p>{graph?.nodes.length} resources · {graph?.edges.length} relationships · revision {String(graph?.metadata.revision || 'unversioned').slice(0, 12)}</p></div><span className={'status-pill ' + review.status}>{review.status}</span></div><ReviewPanel key={review.id} review={review} onChange={updateReview} />{graph && <Suspense fallback={<p>Loading link collaboration...</p>}><CollaborationPanel key={review.id} review={review} graph={graph} catalog={catalog} selected={selected} /></Suspense>}<div className="review-caveat">Review covers this snapshot. Provider gaps and static-analysis limitations remain visible in its evidence.</div></> : <div className="empty-section">Synchronize a managed source to create a reviewable graph snapshot.</div>}</section>}
        {view === 'admin' && <AdminModule />}
        {view === 'connections' && <><Connections catalog={catalog} connectors={connectors} /></>}
        </Suspense>
      </main>
    </IxContent>
  </IxApplication></WorkspaceGraphContext.Provider>
}

function Connections({ catalog, connectors }: { catalog: Catalog | null; connectors: any[] }) {
  return <section className="connections-panel"><div className="connection-intro"><div><p>Manage sources, lifecycle providers and delivery connections in <code>.env.local</code>. Configure session AI in Administration.</p></div><Settings2 size={38} /></div>
    <div className="connection-grid"><ConnectionCard title="Managed repositories" subtitle="MANAGED_REPOSITORIES" icon={<GitBranch size={19} />}>
      {catalog?.sources.map(source => <div className="connection-row" key={source.id}><span><strong>{source.label}</strong><small>{source.kind} · {source.ref || 'Working revision'}</small></span><b>Configured</b></div>)}
    </ConnectionCard><ConnectionCard title="OSLC lifecycle providers" subtitle="OSLC_PROVIDERS" icon={<Network size={19} />}>
      {catalog?.providers.length ? catalog.providers.map(provider => <div className="connection-row" key={provider.id}><span><strong>{provider.label}</strong><small>{provider.domain} · {provider.transport}</small></span><b>{connectors.find(item => item.id === provider.id)?.status || 'Configured'}</b></div>) : <p className="connection-empty">No provider configured. Add AM, RM, CM, TRS, QM or ResourceShape data through managed endpoints or RDF files.</p>}
    </ConnectionCard><ConnectionCard title="Delivery connections" subtitle="CI_PROVIDERS" icon={<Workflow size={19} />}>
      {catalog?.pipelines.length ? catalog.pipelines.map(provider => <div className="connection-row" key={provider.id}><span><strong>{provider.label}</strong><small>{provider.platform}</small></span><b>{connectors.find(item => item.id === provider.id)?.status || 'Configured'}</b></div>) : <p className="connection-empty">No CI connection configured. GitHub Actions and GitLab pipeline adapters are available.</p>}
    </ConnectionCard><ConnectionCard title="Central AI defaults" subtitle="AI_PROVIDER · AI_MODEL" icon={<Sparkles size={19} />}>
      <div className="connection-row"><span><strong>{catalog?.ai.provider || 'Loading'}</strong><small>{catalog?.ai.model || 'No model configured'}</small></span><b>{catalog?.ai.provider === 'disabled' ? 'Disabled' : 'Central default'}</b></div><p className="connection-empty">Override session AI in Administration. Graph tools remain available when the model is offline.</p>
    </ConnectionCard></div>
    <div className="connection-guidance"><ShieldCheck size={17} /><div><strong>Configuration is server managed.</strong><p>Use JSON arrays for catalogs. Provider tokens are referenced by environment-variable name. Restart services after changing settings. This local app does not provide account-based administrative access.</p></div></div>
  </section>
}
function ConnectionCard({ title, subtitle, icon, children }: { title: string; subtitle: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="connection-card"><div className="connection-card-heading">{icon}<h3>{title}</h3></div><code>{subtitle}</code>{children}</div>
}
