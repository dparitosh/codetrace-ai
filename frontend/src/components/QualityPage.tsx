import SourceAnalysisPage from './SourceAnalysisPage'
export default function QualityPage({ onBack }: { onBack: () => void }) {
  return <SourceAnalysisPage title="Quality assessment" description="Structural metrics are review prompts, not proof that code is correct." kind="quality" onBack={onBack}>
    {result => <>
      <div className="flex items-center gap-6"><div className="text-5xl font-bold text-emerald-700">{result.overall_score ?? 'N/A'}</div><b>Grade {result.grade}</b></div>
      <div className="mt-6 divide-y">{result.metrics.map((metric: any) => <div className="flex justify-between py-3" key={metric.name}><span>{metric.name}</span><b>{metric.value ?? 'N/A'}</b></div>)}</div>
      <h2 className="mt-6 font-semibold">Recommendations</h2>
      <ul className="mt-2 list-disc pl-5">{result.recommendations.map((item: string) => <li key={item}>{item}</li>)}</ul>
    </>}
  </SourceAnalysisPage>
}
