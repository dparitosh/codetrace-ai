import SourceAnalysisPage from './SourceAnalysisPage'
interface AnalysisPageProps { onBack: () => void; onNavigateToQuality: () => void; onNavigateToGraph: () => void }
export default function AnalysisPage({ onBack, onNavigateToQuality, onNavigateToGraph }: AnalysisPageProps) {
  return <SourceAnalysisPage title="Local source analysis" description="Supported source files are sent to the local service for analysis and review." kind="analysis" onBack={onBack}>
    {result => <>
      <h2 className="text-xl font-semibold">Analysis complete</h2>
      <div className="mt-4 flex flex-wrap gap-6">
        <span><b>{result.results.summary.total_files}</b> files</span>
        <span><b>{result.results.summary.total_lines}</b> lines</span>
        <span><b>{result.results.graph.edges.length}</b> relationships</span>
      </div>
      <p className="mt-4 text-sm text-slate-600">The other analysis tools use a new folder selection.</p>
      <div className="mt-3 flex gap-3">
        <button onClick={onNavigateToGraph} className="rounded bg-indigo-700 px-4 py-2 text-white">Open graph tool</button>
        <button onClick={onNavigateToQuality} className="rounded bg-emerald-700 px-4 py-2 text-white">Open quality tool</button>
      </div>
    </>}
  </SourceAnalysisPage>
}
