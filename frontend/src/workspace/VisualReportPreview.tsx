import { useEffect, useRef } from 'react'

export type VisualReport = {
  html: string; html_sha256: string
  receipt: { snapshot_id: string | null; review_result_digest: string; analysis_sha256: string }
}

export default function VisualReportPreview({ report, approved, exporting, onClose, onExport }: {
  report: VisualReport; approved: boolean; exporting: boolean; onClose: () => void; onExport: () => void
}) {
  const dialog=useRef<HTMLDialogElement>(null)
  useEffect(()=>{
    const element=dialog.current
    element?.showModal()
    return ()=>{element?.close()}
  },[report])
  return <dialog ref={dialog} className="visual-report-dialog" aria-labelledby="visual-report-title" onCancel={event=>{event.preventDefault();onClose()}}>
    <header className="visual-report-toolbar"><div><h2 id="visual-report-title">Visual optimization report</h2><p>{approved?'Source snapshot approved':'Draft — source snapshot awaits approval'}. Feature mappings and projected savings still require review.</p></div>
      <div className="product-line-actions"><button disabled={!approved || exporting} onClick={onExport}>{exporting?'Exporting…':'Export approved report & evidence'}</button><button autoFocus onClick={onClose}>Close report</button></div>
    </header>
    <p className="visual-report-help">Charts, similarity coefficients, file clusters and cell formation are shown below. Supporting downloads are included in the approved export.</p>
    <iframe title="Visual code optimization assessment" srcDoc={report.html} sandbox="" referrerPolicy="no-referrer" />
  </dialog>
}
