import SourceAnalysisPage from './SourceAnalysisPage'
import { useWorkspaceGraph } from '../workspace/workspaceContext'

export default function AnalysisPage() {
  const { graph } = useWorkspaceGraph()
  const summary = graph?.source_assessments?.summary
  const files = graph?.nodes.filter(node => node.type === 'file') || []
  const types = new Map<string, number>()
  graph?.nodes.filter(node => node.properties.origin === 'code_analyzer' || ['class', 'function', 'method', 'file', 'module', 'package'].includes(node.type)).forEach(node => types.set(node.type, (types.get(node.type) || 0) + 1))
  const languages = new Map<string, number>()
  const extensions: Record<string, string> = { py: 'Python', pyw: 'Python', ts: 'TypeScript', tsx: 'TypeScript', js: 'JavaScript', jsx: 'JavaScript', mjs: 'JavaScript', cjs: 'JavaScript', java: 'Java', cs: 'C#', c: 'C', h: 'C/C++ header', cpp: 'C++', hpp: 'C++ header', go: 'Go', rs: 'Rust', rb: 'Ruby', php: 'PHP', swift: 'Swift', kt: 'Kotlin', sql: 'SQL', json: 'JSON', yaml: 'YAML', yml: 'YAML', xml: 'XML', xsd: 'XML Schema', md: 'Markdown', html: 'HTML', css: 'CSS', scss: 'SCSS', sh: 'Shell', ps1: 'PowerShell' }
  files.forEach(node => { const extension = String(node.properties.path || node.label).split('.').pop()!.toLowerCase(); const language = String(node.properties.language || extensions[extension] || 'Other'); languages.set(language, (languages.get(language) || 0) + 1) })
  return <SourceAnalysisPage title="Source analysis" description="Source inventory, languages and extraction coverage." allowUpload>
    <div className="source-metrics"><span><b>{Number(summary?.total_files ?? graph?.metadata.files ?? files.length).toLocaleString()}</b> files</span><span><b>{summary?.total_lines?.toLocaleString() ?? 'Unavailable'}</b> lines</span><span><b>{graph?.edges.length.toLocaleString() ?? 0}</b> graph relationships</span></div>
    <div className="domain-summary-grid"><section><h2>Extracted structure</h2><dl className="source-metric-list">{[...types].sort((a, b) => b[1] - a[1]).map(([type, count]) => <div key={type}><dt>{type.replace(/_/g, ' ')}</dt><dd>{count.toLocaleString()}</dd></div>)}</dl></section><section><h2>Languages</h2><dl className="source-metric-list">{[...languages].sort((a, b) => b[1] - a[1]).map(([language, count]) => <div key={language}><dt>{language}</dt><dd>{count} files</dd></div>)}</dl><p>Python uses AST extraction; other languages use structural or heuristic extraction.</p></section></div>
    {graph?.metadata.skipped && <p className="source-note">Folder filtering: {graph.metadata.skipped.unsupported || 0} unsupported files, {graph.metadata.skipped.non_utf8 || 0} non-UTF-8 files and {graph.metadata.skipped.excluded_directories || 0} excluded directories.</p>}
  </SourceAnalysisPage>
}
