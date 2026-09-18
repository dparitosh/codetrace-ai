import { useState } from 'react'
import { FolderOpen, GitBranch, Play, ArrowLeft } from 'lucide-react'
import { API_CONFIG } from '../config/api'

interface GraphPageProps { onBack: () => void }

const readFiles = (files: File[]) => Promise.all(files.map(async file => ({ path: file.webkitRelativePath || file.name, content: await file.text(), size: file.size, last_modified: file.lastModified })))

function GraphCanvas({ graph }: { graph: any }) {
  const nodes = (graph?.nodes || []).slice(0, 100)
  const edges = (graph?.edges || []).slice(0, 220)
  const width = 1400, height = 900
  const positions = new Map<string, { x: number; y: number }>(nodes.map((node: any, index: number): [string, { x: number; y: number }] => {
    const angle = index / Math.max(nodes.length, 1) * Math.PI * 2 - Math.PI / 2
    return [String(node.id), { x: width / 2 + Math.cos(angle) * 540, y: height / 2 + Math.sin(angle) * 340 }]
  }))
  const color = (type: string) => type === 'function' ? ['#dcfce7', '#16a34a'] : type === 'class' ? ['#ede9fe', '#7c3aed'] : type === 'package' ? ['#fef3c7', '#d97706'] : ['#dbeafe', '#2563eb']
  return <div className="h-[72vh] min-h-[620px] w-full overflow-auto rounded-xl border border-slate-200 bg-white">
    {graph.nodes.length > nodes.length && <p className="p-2 text-sm text-amber-800">Preview shows {nodes.length} of {graph.nodes.length} nodes and up to 220 relationships.</p>}
    <svg viewBox={`0 0 ${width} ${height}`} className="h-full min-w-[1000px] w-full" role="img" aria-label="Dependency graph">
      <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="#94a3b8" /></marker></defs>
      {edges.map((edge: any, index: number) => { const from = positions.get(String(edge.source)), to = positions.get(String(edge.target)); return from && to ? <line key={index} x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#cbd5e1" strokeWidth="1.5" markerEnd="url(#arrow)" /> : null })}
      {nodes.map((node: any) => { const p = positions.get(String(node.id)); if (!p) return null; const [fill, stroke] = color(node.type); return <g key={node.id}><circle cx={p.x} cy={p.y} r="20" fill={fill} stroke={stroke} strokeWidth="2" /><text x={p.x} y={p.y + 34} textAnchor="middle" fontSize="11" fill="#334155">{String(node.label || node.id).slice(0, 28)}</text></g> })}
    </svg>
  </div>
}

export default function GraphPage({ onBack }: GraphPageProps) {
  const [files, setFiles] = useState<File[]>([])
  const [gitlabUrl, setGitlabUrl] = useState('')
  const [graph, setGraph] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const generate = async () => {
    if (!files.length && !gitlabUrl.trim()) return setError('Select a folder or enter a GitLab project URL.')
    setLoading(true); setError(''); setGraph(null)
    try {
      const local = files.length > 0
      const response = await fetch(local ? API_CONFIG.GRAPH.LOCAL : API_CONFIG.GRAPH.GITLAB, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(local ? { files: await readFiles(files) } : { project_url: gitlabUrl.trim() }) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || result.detail || 'Graph generation failed')
      setGraph(result)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Graph generation failed') } finally { setLoading(false) }
  }

  return <main className="min-h-screen bg-slate-50 p-6 lg:p-8"><div className="mx-auto max-w-[1600px]">
    <button onClick={onBack} className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-indigo-700"><ArrowLeft className="h-4 w-4" />Dashboard</button>
    <h1 className="text-3xl font-bold text-slate-900">Dependency graph</h1><p className="mt-1 text-slate-600">Analyze a selected folder or a GitLab project. Local folders are the default.</p>
    <section className="mt-6 grid gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:grid-cols-[1fr_1fr_auto] lg:items-end">
      <label className="block text-sm font-medium text-slate-700">Local source folder<input type="file" multiple ref={input => input?.setAttribute('webkitdirectory', '')} onChange={event => setFiles(Array.from(event.target.files || []))} className="mt-2 block w-full text-sm" />{files.length > 0 && <span className="mt-2 block text-emerald-700">{files.length} files selected</span>}</label>
      <label className="block text-sm font-medium text-slate-700">GitLab project URL (optional)<input value={gitlabUrl} onChange={event => setGitlabUrl(event.target.value)} placeholder="https://gitlab.com/group/project" type="url" className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2" disabled={files.length > 0} /></label>
      <button onClick={generate} disabled={loading} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 font-medium text-white disabled:opacity-50">{files.length ? <FolderOpen className="h-4 w-4" /> : <GitBranch className="h-4 w-4" />}{loading ? 'Generating…' : 'Generate graph'}</button>
    </section>
    {error && <p className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-red-700">{error}</p>}
    {graph && <section className="mt-6"><div className="mb-3 flex flex-wrap gap-5 text-sm text-slate-600"><span><b>{graph.nodes?.length || 0}</b> nodes</span><span><b>{graph.edges?.length || 0}</b> edges</span><span>{graph.metadata?.source === 'gitlab' ? 'GitLab project' : 'Local folder'}</span></div><GraphCanvas graph={graph} /></section>}
    {!graph && !loading && <div className="mt-6 flex h-[72vh] min-h-[620px] items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-white text-slate-500"><Play className="mr-2 h-5 w-5" />Select a folder to render its code graph.</div>}
  </div></main>
}
