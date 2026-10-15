import { IxButton } from '@siemens/ix-react'
import { useEffect, useState } from 'react'
import { decideReview, exportReview, exportWorkspaceSbom, getReview, ReviewRecord, useReviewSession } from '../reviewSession'

export default function ReviewPanel({ review, onChange }: { review: ReviewRecord; onChange: (review: ReviewRecord) => void }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const session = useReviewSession()
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!session) return
    const timer = setTimeout(() => setNow(Date.now()), Math.max(0, session.deadline - Date.now()) + 10)
    return () => clearTimeout(timer)
  }, [session])
  const expired = !session || session.token !== review.sessionToken || session.deadline <= now
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try { await action() } catch (cause) { setError(cause instanceof Error ? cause.message : 'Review action failed') }
    finally { setBusy(false) }
  }
  return <section className="mt-5 rounded-xl border border-indigo-200 bg-white p-5" aria-label="Result review">
    <h2 className="text-xl font-semibold">Review: {review.status}</h2>
    <p className="mt-1 text-sm text-slate-600">Local reviewer decision for this exact result. It does not certify that the code is bug-free.</p>
    <p className="mt-2 text-sm">Analysis time: {review.elapsed_seconds ?? '—'} seconds</p>
    {review.status === 'pending' && <label className="mt-3 block">Review notes
      <textarea value={note} maxLength={2000} onChange={event => setNote(event.target.value)} className="mt-1 block w-full rounded border p-2" />
    </label>}
    <div className="mt-3 flex flex-wrap gap-3">
      {review.status === 'pending' && <>
        <IxButton disabled={busy || expired} onClick={() => run(async () => onChange(await decideReview(review, 'approved', note)))} className="rounded bg-emerald-700 px-4 py-2 text-white disabled:opacity-50">Approve result</IxButton>
        <IxButton disabled={busy || expired} onClick={() => run(async () => onChange(await decideReview(review, 'rejected', note)))} className="rounded bg-red-700 px-4 py-2 text-white disabled:opacity-50">Reject result</IxButton>
      </>}
      <IxButton disabled={busy || expired} onClick={() => run(async () => onChange(await getReview(review.id)))} className="rounded border px-4 py-2 disabled:opacity-50">Refresh review</IxButton>
      <IxButton disabled={busy || expired || review.status !== 'approved'} onClick={() => run(() => exportReview(review.id))} className="rounded bg-indigo-700 px-4 py-2 text-white disabled:opacity-50">Download approved result</IxButton>
      {review.result?.sbom && <IxButton disabled={busy || expired || review.status !== 'approved'} onClick={() => run(() => exportWorkspaceSbom(review))}>Download approved SBOM</IxButton>}
    </div>
    {expired && <p className="mt-3 text-amber-800">Session expired or ended. This displayed result cannot be approved or exported; start a new analysis.</p>}
    {error && <p role="alert" className="mt-3 text-red-700">{error}</p>}
    <details className="mt-4"><summary>Audit history ({review.audit.length})</summary>
      <ol className="mt-2 space-y-2">{review.audit.map((event, index) => <li key={index}>
        {event.action} · {new Date(event.at).toLocaleString()} {event.note && <span>— {event.note}</span>}
      </li>)}</ol>
      <p className="mt-2 break-all text-xs text-slate-500">Result digest: {review.result_digest}</p>
    </details>
  </section>
}
