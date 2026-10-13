import SourceAnalysisPage from './SourceAnalysisPage'
export default function SecurityPage() {
  return <SourceAnalysisPage title="Local security scan" description="Static checks for possible secrets and dynamic execution in supported source files." kind="security">
    {result => <>
      <h2 className="text-xl font-semibold">{result.total_findings} finding(s) in {result.files_scanned} files</h2>
      {result.truncated && <p className="mt-3 text-amber-800">Showing {result.findings.length} of {result.total_findings} findings. Scan smaller source selections to inspect the remaining findings.</p>}
      {result.total_findings === 0 ? <p className="mt-4 text-emerald-700">No matching static security patterns were found.</p> :
        <div className="mt-4 divide-y">{result.findings.map((finding: any, index: number) => <div className="py-3" key={`${finding.file}-${finding.line}-${index}`}>
          <b className="text-red-700">{finding.severity}</b><span className="ml-3">{finding.description}</span><p className="text-sm text-slate-500">{finding.file}:{finding.line}</p>
        </div>)}</div>}
    </>}
  </SourceAnalysisPage>
}
