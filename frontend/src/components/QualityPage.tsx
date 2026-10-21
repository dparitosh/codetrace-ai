import SourceAnalysisPage from './SourceAnalysisPage'
import { useWorkspaceGraph } from '../workspace/workspaceContext'

export default function QualityPage() {
  const { graph } = useWorkspaceGraph()
  const quality = graph?.source_assessments?.quality
  return <SourceAnalysisPage title="Quality assessment" description="Structural scores and recommended improvements; these do not establish correctness.">
    {quality ? <><div className="source-metrics"><span><b>{quality.overall_score ?? 'N/A'}</b> structural score</span><span><b>{quality.grade}</b> grade</span></div>
      <dl className="source-metric-list">{quality.metrics.map(metric => <div key={metric.name}><dt>{metric.name}<small>{metric.description}</small></dt><dd>{metric.value ?? 'N/A'} · {metric.status}</dd></div>)}</dl>
      <ul>{quality.recommendations.map(item => <li key={item}>{item}</li>)}</ul></> : <p>Quality evidence is unavailable in this older snapshot. Synchronize the source to generate it.</p>}
  </SourceAnalysisPage>
}
