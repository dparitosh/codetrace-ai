// Dependency-free session race contracts for Node 22.13+.
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { test } from 'node:test'
import assert from 'node:assert/strict'

globalThis.__APP_CONFIG__ = { controlTimeout: 1 }
const json = data => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
const timing = { expires_in_seconds: 60, absolute_remaining_seconds: 120 }
let version = 0
async function client() {
  const source = stripTypeScriptTypes(readFileSync(new URL('./src/reviewSession.ts', import.meta.url), 'utf8'))
    .replace("import { useSyncExternalStore } from 'react'", 'const useSyncExternalStore = () => null')
  return import('data:text/javascript;base64,' + Buffer.from(source + '\n// version ' + version++).toString('base64'))
}
test('ending during session creation cannot resurrect the session', async () => {
  let resolve
  globalThis.fetch = () => new Promise(done => { resolve = done })
  const api = await client()
  const pending = api.startSession()
  await api.endSession()
  resolve(json({ token: 'old', ...timing }))
  await assert.rejects(pending, /cancelled/)
})
test('a late approval response is rejected after ending its session', async () => {
  let resolve
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/decision')) return new Promise(done => { resolve = done })
    return json({ token: 'one', ...timing })
  }
  const api = await client()
  await api.startSession()
  const pending = api.decideReview({ id: 'r', sessionToken: 'one' }, 'approved', '')
  await api.endSession()
  resolve(json({ id: 'r', status: 'approved' }))
  await assert.rejects(pending, /Session changed/)
})
test('concurrent starts share one server session', async () => {
  let calls = 0
  globalThis.fetch = async () => { calls++; return json({ token: 'one', ...timing }) }
  const api = await client()
  const results = await Promise.all([api.startSession(), api.startSession()])
  assert.equal(calls, 1)
  assert.equal(results[0].token, results[1].token)
})
