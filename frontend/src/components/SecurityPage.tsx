import SourceAnalysisPage from './SourceAnalysisPage'
import { useWorkspaceGraph } from '../workspace/workspaceContext'

export default function SecurityPage() {
  const { graph, select } = useWorkspaceGraph()
  const security = graph?.source_assessments?.security
  const inspect = (path: string) => {
    const node = graph?.nodes.find(item => item.type === 'file' && item.properties.path === path)
    if (node) select(node)
  }
  return <SourceAnalysisPage title="Security patterns" description="Static security pattern findings; coverage is limited to configured rules.">
    {security ? <><h3>{security.total_findings} findings in {security.files_scanned} files</h3>
      {security.truncated && <p>Showing {security.findings.length} of {security.total_findings} findings. Analyze a smaller selection to inspect the rest.</p>}
      {security.total_findings === 0 ? <p>No matching static security patterns were found.</p> : <ul className="source-findings">{security.findings.map((finding, index) => <li key={`${finding.file}:${finding.line}:${index}`}>
        <strong>{finding.severity} · {finding.description}</strong><button onClick={() => inspect(finding.file)}>{finding.file}:{finding.line}</button>
      </li>)}</ul>}</> : <p>Security evidence is unavailable in this older snapshot. Synchronize the source to generate it.</p>}
  </SourceAnalysisPage>
}
