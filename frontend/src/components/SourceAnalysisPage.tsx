import { ReactNode, useEffect, useState } from 'react'
import { IxButton } from '@siemens/ix-react'
import { useWorkspaceGraph } from '../workspace/workspaceContext'

interface Props { title: string; description: string; children: ReactNode; allowUpload?: boolean }
export default function SourceAnalysisPage({ title, description, children, allowUpload = false }: Props) {
  const { graph, review, sourceLabel, busy, notice, analyzeUpload } = useWorkspaceGraph()
  const [files, setFiles] = useState<File[]>([])
  useEffect(() => setFiles([]), [review?.sessionToken, sourceLabel])
  return <section className="source-context-panel" aria-label={title}>
    <p className="page-purpose">{description}</p>
    {!graph && <div className="empty-section"><h2>No source evidence yet</h2><p>Use Synchronize to analyze the configured source.</p></div>}
    {graph && children}
    {allowUpload && <details className="source-upload"><summary>Analyze a different folder</summary><p>Replaces this snapshot. Synchronize to return to the configured source.</p>
      <label>Local source folder<input type="file" multiple disabled={busy} ref={input => input?.setAttribute('webkitdirectory', '')}
        onChange={event => setFiles(Array.from(event.target.files || []))} /></label>
      <IxButton disabled={busy || !files.length} onClick={async () => { if (await analyzeUpload(files)) setFiles([]) }}>{busy ? 'Analyzing…' : 'Analyze folder into workspace'}</IxButton>
    </details>}
    {notice && <p role="status">{notice}</p>}
  </section>
}
