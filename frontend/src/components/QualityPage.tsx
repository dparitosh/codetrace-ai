import SourceAnalysisPage from './SourceAnalysisPage'
import { useWorkspaceGraph } from '../workspace/workspaceContext'

export default function QualityPage() {
  const { graph } = useWorkspaceGraph()
  const quality = graph?.source_assessments?.quality
  const structuralMetrics = quality?.metrics.filter(metric => metric.name !== 'Documentation coverage') || []
  const documentationMetrics = quality?.metrics.filter(metric => metric.name === 'Documentation coverage') || []
  return <SourceAnalysisPage title="Quality assessment" description="Structural scores and recommended improvements; these do not establish correctness.">
    {quality ? <><h3>Structural quality</h3><div className="source-metrics"><span><b>{quality.overall_score ?? 'Not scored'}</b> structural score</span>{quality.overall_score !== null && <span><b>{quality.grade}</b> grade</span>}</div>
      <p>{quality.scoring_basis || 'This snapshot predates scoring details. Synchronize the source to refresh the assessment.'}</p>
      <dl className="source-metric-list">{structuralMetrics.map(metric => <div key={metric.name}><dt>{metric.name}<small>{metric.description}</small></dt><dd>{metric.value ?? 'Not measurable'} · {metric.status}</dd></div>)}</dl>
      {documentationMetrics.length > 0 && <section aria-label="Documentation assessment"><h3>Documentation</h3><p>Reported independently; excluded from the structural score and grade. Synchronize older snapshots to apply this scoring rule.</p>
        <dl className="source-metric-list">{documentationMetrics.map(metric => <div key={metric.name}><dt>{metric.name}<small>{metric.description}</small></dt><dd>{metric.value === null ? 'Not measurable' : `${metric.value}%`} · {metric.status}</dd></div>)}</dl></section>}
      <ul>{quality.recommendations.map(item => <li key={item}>{item}</li>)}</ul></> : <p>Quality evidence is unavailable in this older snapshot. Synchronize the source to generate it.</p>}
  </SourceAnalysisPage>
}
