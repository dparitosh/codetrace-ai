import { IxButton } from '@siemens/ix-react'
import { lazy, Suspense, memo, useEffect, useMemo, useState } from 'react'
import { endSession, getReview, listReviews, refreshSession, ReviewRecord, startSession, useReviewSession } from '../reviewSession'
const ReviewPanel = lazy(() => import('./ReviewPanel'))

const ResultPreview = memo(function ResultPreview({ result }: { result: unknown }) {
  const [open, setOpen] = useState(false)
  const limit = __APP_CONFIG__.reviewPreviewItems
  const preview = useMemo(() => open ? JSON.stringify(result, (_key, value) =>
    Array.isArray(value) && value.length > limit ? [...value.slice(0, limit), { omitted_items: value.length - limit }] : value, 2) : '', [result, open, limit])
  return <section className="mt-3">
    <IxButton className="underline" onClick={() => setOpen(value => !value)}>{open ? 'Hide' : 'Inspect'} result preview</IxButton>
    {open && <><p className="text-sm">Preview limited to {limit} items per list. Approved exports contain the full result.</p><pre className="max-h-96 overflow-auto bg-white p-3 text-xs">{preview}</pre></>}
  </section>
})

export default function SessionBar() {
  const session = useReviewSession()
  const [now, setNow] = useState(Date.now())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [reviews, setReviews] = useState<ReviewRecord[] | null>(null)
  const [selected, setSelected] = useState<ReviewRecord | null>(null)
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer) }, [])
  useEffect(() => { setReviews(null); setSelected(null) }, [session?.token])
  const remaining = session ? Math.max(0, Math.ceil((session.deadline - Math.max(now, Date.now())) / 1000)) : 0
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try { await action() } catch (cause) { setError(cause instanceof Error ? cause.message : 'Session action failed') }
    finally { setBusy(false) }
  }
  return <aside className="session-toolbar" aria-label="Review session">
    <div className="flex flex-wrap items-center gap-4 text-sm">
      <b>{remaining ? `Session expires in ${Math.floor(remaining / 60)}m ${remaining % 60}s` : 'No active review session'}</b>
      {remaining ? <>
        <IxButton variant="tertiary" disabled={busy} onClick={() => run(() => refreshSession(true))}>Extend</IxButton>
        <IxButton variant="tertiary" disabled={busy} onClick={() => run(async () => setReviews(await listReviews()))}>History</IxButton>
        <IxButton variant="tertiary" disabled={busy} onClick={() => run(endSession)} aria-label="End session and clear reviews">End session</IxButton>
      </> : <IxButton disabled={busy} onClick={() => run(startSession)} className="underline">Start session</IxButton>}
      <details className="session-retention"><summary>Retention</summary><p>{session?.retention || 'Reviews are cleared when the session ends or expires.'}</p></details>
    </div>
    {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
    {reviews && remaining > 0 && <div className="mt-3 flex flex-wrap gap-3">
      {!reviews.length && <span>No reviews yet.</span>}
      {reviews.map(review => <IxButton key={review.id} disabled={busy || review.status === 'processing'}
        onClick={() => run(async () => setSelected(await getReview(review.id)))} className="rounded border bg-white px-3 py-2">
        {review.kind} · {review.status} · {new Date(review.created_at).toLocaleTimeString()}
      </IxButton>)}
      <IxButton onClick={() => { setReviews(null); setSelected(null) }} className="underline">Close history</IxButton>
    </div>}
    {selected && remaining > 0 && <Suspense fallback={<p>Loading review...</p>}>
      <ReviewPanel key={selected.id} review={selected} onChange={value => {
        setSelected(value); setReviews(items => items?.map(item => item.id === value.id ? value : item) || null)
      }} />
      <ResultPreview result={selected.result} />
    </Suspense>}
  </aside>
}
