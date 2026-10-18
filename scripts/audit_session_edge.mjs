// Read-only reproduction for a session ending during a timing refresh.
// Run: node scripts/audit_session_edge.mjs
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'

globalThis.__APP_CONFIG__ = { controlTimeout: 5 }
const json = data => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
const timing = { expires_in_seconds: 60, absolute_remaining_seconds: 120 }
const source = stripTypeScriptTypes(readFileSync(new URL('../frontend/src/reviewSession.ts', import.meta.url), 'utf8'))
  .replace("import { useSyncExternalStore } from 'react'", 'const useSyncExternalStore = () => null')
const api = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
let releaseTiming, enteredTiming
const timingStarted = new Promise(resolve => { enteredTiming = resolve })
globalThis.fetch = async (url, options) => {
  if (url.endsWith('/sync')) return json({ id: 'fixture', result: { nodes: [] } })
  if (options?.method === 'DELETE') return json({ ended: true })
  if (options?.method === 'POST') return json({ token: 'fixture-session', ...timing })
  enteredTiming()
  return new Promise(resolve => { releaseTiming = resolve })
}
const pending = api.workspaceRequest('sync', {}, 5)
await timingStarted
await api.endSession()
releaseTiming(json(timing))
try {
  await pending
  console.log('A32 | FAIL | A result is returned after its session ended during the timing refresh')
} catch {
  console.log('A32 | PASS | Late result rejected')
}
