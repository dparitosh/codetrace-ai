import { ReactNode, useEffect, useState } from 'react'
import { ArrowLeft, FolderOpen } from 'lucide-react'
import { loadSourceConfiguration, readSourceFiles } from '../sourceFiles'
import { ReviewRecord, submitForReview, useReviewSession } from '../reviewSession'
import ReviewPanel from './ReviewPanel'

interface Props {
  title: string
  description: string
  kind: 'analysis' | 'quality' | 'security'
  onBack?: () => void
  children: (result: any) => ReactNode
}

export default function SourceAnalysisPage({ title, description, kind, onBack, children }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [review, setReview] = useState<ReviewRecord | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const session = useReviewSession()
  useEffect(() => {
    const clear = () => { if (review && (!session || session.token !== review.sessionToken || session.deadline <= Date.now())) { setReview(null); setFiles([]) } }
    clear(); const timer = setInterval(clear, 1000); return () => clearInterval(timer)
  }, [session, review])
  const analyze = async () => {
    if (!files.length) { setError('Select a local source folder.'); return }
    setLoading(true); setError(''); setNotice(''); setReview(null)
    try {
      const config = await loadSourceConfiguration()
      const source = { files: await readSourceFiles(files, setNotice, config) }
      setReview(await submitForReview(kind, source, config.request_timeout_seconds))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Analysis failed') }
    finally { setLoading(false) }
  }
  return <main className="min-h-screen bg-slate-50 p-6"><div className="mx-auto max-w-5xl">
    {onBack && <button onClick={onBack} className="mb-5 inline-flex items-center gap-2 text-indigo-700"><ArrowLeft className="h-4 w-4" />Dashboard</button>}
    <h1 className="text-3xl font-bold">{title}</h1><p className="mt-1 text-slate-600">{description}</p>
    <section className="mt-6 rounded-xl bg-white p-6 shadow-sm">
      <label className="block font-medium">Source folder<input type="file" multiple disabled={loading}
        ref={input => input?.setAttribute('webkitdirectory', '')}
        onChange={event => { setFiles(Array.from(event.target.files || [])); setReview(null); setError(''); setNotice('') }}
        className="mt-3 block" /></label>
      {files.length > 0 && <p className="mt-2 text-emerald-700">{files.length} files selected before filtering</p>}
      <button onClick={analyze} disabled={loading} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-indigo-700 px-5 py-2.5 text-white disabled:opacity-50">
        <FolderOpen className="h-4 w-4" />{loading ? 'Analyzing…' : 'Analyze and submit for review'}
      </button>
      {notice && <p className="mt-3 text-amber-800">{notice}</p>}
      {error && <p role="alert" className="mt-4 text-red-700">{error}</p>}
    </section>
    {review && <>
      <section className="mt-6 rounded-xl bg-white p-6 shadow-sm">{children(review.result)}</section>
      <ReviewPanel key={review.id} review={review} onChange={setReview} />
    </>}
  </div></main>
}
