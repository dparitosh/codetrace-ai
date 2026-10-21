import { useSyncExternalStore } from 'react'

export interface ReviewRecord {
  id: string
  kind: string
  status: 'processing' | 'pending' | 'approved' | 'rejected'
  revision: number
  result_digest: string
  created_at: string
  elapsed_seconds?: number
  result?: any
  audit: { action: string; at: string; note: string; result_digest: string }[]
  sessionToken?: string
}

type Session = { token: string; deadline: number; absoluteDeadline: number; retention?: string }
let session: Session | null = null
let creating: Promise<Session> | null = null
let generation = 0
const listeners = new Set<() => void>()
const reviewListeners = new Set<(record: ReviewRecord) => void>()
export function subscribeReviewChanges(listener: (record: ReviewRecord) => void) {
  reviewListeners.add(listener)
  return () => { reviewListeners.delete(listener) }
}
const base = '/api/v1/review'
const notify = () => listeners.forEach(listener => listener())
export const useReviewSession = () => useSyncExternalStore(
  listener => { listeners.add(listener); return () => { listeners.delete(listener) } },
  () => session,
)

// Control requests use shared configuration; analysis uses the server's current deadline.
export async function requestJson(url: string, options: RequestInit = {}, timeoutSeconds = __APP_CONFIG__.controlTimeout): Promise<any> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutSeconds * 1000)
  try {
    const response = await fetch(url, { ...options, signal: controller.signal })
    const data = await response.json()
    if (!response.ok) {
      if (response.status === 401 && (url.startsWith(base) || url.startsWith('/api/v1/workspace') || url.startsWith('/api/v1/oslc')) && new Headers(options.headers).get('X-CodeTrace-Session') === session?.token) { generation++; session = null; notify() }
      throw new Error(typeof data.error === 'string' ? data.error : typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || 'Request failed'))
    }
    return data
  } catch (error) {
    if (controller.signal.aborted) throw new Error('Request timed out. The server may still be processing it; refresh review history before retrying.')
    throw error
  } finally { clearTimeout(timer) }
}

function updateTiming(token: string, data: any) {
  session = { token, deadline: Date.now() + data.expires_in_seconds * 1000,
    absoluteDeadline: Date.now() + data.absolute_remaining_seconds * 1000, retention: data.retention }
  notify()
  return session
}

export async function startSession() {
  if (session && session.deadline > Date.now()) return session
  if (!creating) {
    const expectedGeneration = generation
    creating = requestJson(`${base}/session`, { method: 'POST' })
      .then(data => {
        if (expectedGeneration !== generation) throw new Error('Session creation was cancelled.')
        return updateTiming(data.token, data)
      }).finally(() => { creating = null })
  }
  return creating
}

function headers(token: string) { return { 'Content-Type': 'application/json', 'X-CodeTrace-Session': token } }

function activeSession() {
  if (!session || session.deadline <= Date.now()) throw new Error('Session expired. Start a new session and run the analysis again.')
  return session
}

export async function refreshSession(keepAlive = false) {
  const current = session
  if (!current) throw new Error('No active review session.')
  const data = await requestJson(`${base}/session${keepAlive ? '/keepalive' : ''}`,
    { method: keepAlive ? 'POST' : 'GET', headers: headers(current.token) })
  if (session?.token === current.token) updateTiming(current.token, data)
}

export async function endSession() {
  generation++
  if (!session) return
  const current = session
  await requestJson(`${base}/session`, { method: 'DELETE', headers: headers(current.token) })
  if (session?.token === current.token) { session = null; notify() }
}

export async function submitForReview(kind: string, source: unknown, timeout: number, manifest?: unknown): Promise<ReviewRecord> {
  const current = await startSession()
  const result = await requestJson(`${base}/reviews`, { method: 'POST', headers: headers(current.token),
    body: JSON.stringify({ request_id: crypto.randomUUID(), kind, source, ...(manifest ? { manifest } : {}) }) }, timeout)
  if (session?.token !== current.token) throw new Error('The analysis belongs to an ended session. Run it again in the current session.')
  // A lost timing refresh should not hide a successfully computed result.
  await refreshSession().catch(() => undefined)
  if (session?.token !== current.token || (session?.deadline || 0) <= Date.now()) throw new Error('Session ended or expired while refreshing the result.')
  return { ...result, sessionToken: current.token }
}

export async function listReviews(): Promise<ReviewRecord[]> {
  const current = activeSession()
  const result = await requestJson(`${base}/reviews`, { headers: headers(current.token) })
  if (session?.token !== current.token) throw new Error('Session changed while loading review history.')
  return result
}

export async function getReview(id: string): Promise<ReviewRecord> {
  const current = activeSession()
  const result = await requestJson(`${base}/reviews/${encodeURIComponent(id)}`, { headers: headers(current.token) })
  if (session?.token !== current.token) throw new Error('Session changed while loading the review.')
  await refreshSession().catch(() => undefined)
  if (session?.token !== current.token || (session?.deadline || 0) <= Date.now()) throw new Error('Session ended or expired while refreshing the result.')
  return { ...result, sessionToken: current.token }
}

export async function decideReview(record: ReviewRecord, action: 'approved' | 'rejected', note: string): Promise<ReviewRecord> {
  const current = activeSession()
  if (record.sessionToken !== current.token) throw new Error('This review belongs to a previous session.')
  const result = await requestJson(`${base}/reviews/${encodeURIComponent(record.id)}/decision`, {
    method: 'POST', headers: headers(current.token),
    body: JSON.stringify({ action, note, revision: record.revision, result_digest: record.result_digest }),
  })
  if (session?.token !== current.token) throw new Error('Session changed while deciding the review.')
  await refreshSession().catch(() => undefined)
  if (session?.token !== current.token || (session?.deadline || 0) <= Date.now()) throw new Error('Session ended or expired while refreshing the result.')
  const updated = { ...result, sessionToken: current.token }
  reviewListeners.forEach(listener => listener(updated))
  return updated
}

export async function exportReview(id: string) {
  const current = activeSession()
  const data = await requestJson(`${base}/reviews/${encodeURIComponent(id)}/export`, { headers: headers(current.token) })
  if (session?.token !== current.token) throw new Error('Session changed while exporting the review.')
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url; link.download = 'codetrace-approved-review.json'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  await refreshSession().catch(() => undefined)
}

export async function exportWorkspaceSbom(record: ReviewRecord) {
  const current = activeSession()
  if (record.sessionToken !== current.token) throw new Error('This review belongs to a previous session.')
  const data = await requestJson('/api/v1/workspace/sbom/' + encodeURIComponent(record.id), { headers: headers(current.token) })
  if (session?.token !== current.token) throw new Error('Session changed while exporting the SBOM.')
  const url = URL.createObjectURL(new Blob([JSON.stringify(data.document, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url; link.download = 'codetrace-approved-sbom.json'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  await refreshSession().catch(() => undefined)
}

export async function workspaceRequest<T>(path: string, body: unknown, timeout: number, expectedSession?: string): Promise<T> {
  const current = await startSession()
  if (expectedSession && expectedSession !== current.token) throw new Error('The graph belongs to a previous session. Synchronize the source again.')
  const result = await requestJson('/api/v1/workspace/' + path, { method: 'POST', headers: headers(current.token), body: JSON.stringify(body) }, timeout)
  if (session?.token !== current.token) throw new Error('The session changed during this request.')
  await refreshSession().catch(() => undefined)
  if (session?.token !== current.token || (session?.deadline || 0) <= Date.now()) throw new Error('The session ended or expired during this request.')
  return { ...result, sessionToken: current.token }
}

export async function aiRequest<T>(path: string, method = 'GET', body?: unknown, timeout = __APP_CONFIG__.controlTimeout): Promise<T> {
  const current = await startSession()
  const result = await requestJson('/api/v1/workspace/ai/' + path, { method, headers: headers(current.token),
    ...(body === undefined ? {} : { body: JSON.stringify(body) }) }, timeout)
  if (session?.token !== current.token) throw new Error('AI settings belong to an ended session.')
  await refreshSession().catch(() => undefined)
  if (session?.token !== current.token || (session?.deadline || 0) <= Date.now()) throw new Error('The session changed during this request.')
  return result
}

export async function collaborationRequest<T>(path: string, expectedSession: string | undefined, body?: unknown, timeout = __APP_CONFIG__.controlTimeout): Promise<T> {
  const current = activeSession()
  if (current.token !== expectedSession) throw new Error('This graph belongs to a previous session.')
  const result = await requestJson('/api/v1/oslc/' + path, {
    method: body === undefined ? 'GET' : 'POST', headers: headers(current.token),
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  }, timeout)
  if (session?.token !== current.token || current.deadline <= Date.now()) throw new Error('Session expired or changed during collaboration.')
  await refreshSession().catch(() => undefined)
  return result
}
