import { useEffect, useState } from 'react'
import { IxButton } from '@siemens/ix-react'
import { aiRequest, useReviewSession } from '../reviewSession'

export interface AIProfile {
  enabled: boolean; base_url: string; model: string; embedding_model: string; key_header: string
  embeddings_enabled: boolean; key_configured: boolean; allowed_base_urls?: string[]; request_timeout_seconds?: number
  agents?: { id: string; label: string; description: string; tools: string[] }[]
}

export default function AISettings() {
  const session = useReviewSession()
  const token = session?.token
  const deadline = session?.deadline
  const [profile, setProfile] = useState<AIProfile | null>(null)
  const [key, setKey] = useState(''), [clearKey, setClearKey] = useState(false)
  const [models, setModels] = useState<string[]>([])
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('')
  useEffect(() => {
    let active = true
    setProfile(null); setKey(''); setModels([]); setMessage('')
    if (token) aiRequest<AIProfile>('config').then(value => { if (active) setProfile(value) }).catch(cause => { if (active) setMessage(String(cause)) })
    return () => { active = false }
  }, [token])
  useEffect(() => {
    if (!deadline) return
    const timer = setTimeout(() => { setProfile(null); setKey(''); setModels([]); setMessage('Session expired. Start a session to configure AI again.') }, Math.max(0, deadline - Date.now()) + 10)
    return () => clearTimeout(timer)
  }, [deadline])
  const load = async () => { setProfile(await aiRequest<AIProfile>('config')) }
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setMessage('')
    try { await action() } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'AI configuration failed') }
    finally { setBusy(false) }
  }
  const save = async () => {
    if (!profile) return
    const { enabled, base_url, model, embedding_model, key_header, embeddings_enabled } = profile
    const result = await aiRequest<AIProfile>('config', 'PUT', { enabled, base_url, model, embedding_model, key_header, embeddings_enabled, api_key: key, keep_key: !clearKey })
    setProfile(current => current ? { ...current, ...result } : result); setKey(''); setClearKey(false)
    window.dispatchEvent(new Event('codetrace:ai-config'))
  }
  return <section className="ai-settings" aria-label="Ollama AI configuration">
    <span className="eyebrow">AGENT RUNTIME</span><h2>Connect Ollama REST</h2>
    <p>Register your chat model and Nomic embedding model for this review session. Keys stay on the server and are never stored in browser storage or returned by this form.</p>
    {!profile ? <IxButton disabled={busy} onClick={() => run(load)}>Start session and load AI settings</IxButton> : <>
      <label><input type="checkbox" checked={profile.enabled} onChange={event => setProfile({ ...profile, enabled: event.target.checked })} />Enable Ollama agent execution</label>
      <div className="ai-settings-grid">
        <label>Ollama REST URL<input aria-label="Ollama REST URL" value={profile.base_url} maxLength={2048} onChange={event => setProfile({ ...profile, base_url: event.target.value })} placeholder="http://127.0.0.1:11434" /></label>
        <label>Key header<select aria-label="Ollama key header" value={profile.key_header} onChange={event => setProfile({ ...profile, key_header: event.target.value })}><option>Authorization</option><option>api-key</option><option>Ocp-Apim-Subscription-Key</option></select></label>
        <label>API key<input aria-label="Ollama API key" type="password" autoComplete="off" value={key} maxLength={4096} onChange={event => setKey(event.target.value)} placeholder={profile.key_configured ? 'Saved key retained when blank' : 'Optional for local Ollama'} /></label>
        <label><input type="checkbox" checked={clearKey} onChange={event => setClearKey(event.target.checked)} />Remove saved key when saving</label>
        <label>Chat model<input aria-label="Ollama chat model" list="ollama-models" value={profile.model} maxLength={160} onChange={event => setProfile({ ...profile, model: event.target.value })} placeholder="Select an installed tool-capable model" /></label>
        <label>Embedding model<input aria-label="Ollama embedding model" list="ollama-models" value={profile.embedding_model} maxLength={160} onChange={event => setProfile({ ...profile, embedding_model: event.target.value })} placeholder="nomic-embed-text" /></label>
      </div>
      <datalist id="ollama-models">{models.map(model => <option key={model} value={model} />)}</datalist>
      <label><input type="checkbox" checked={profile.embeddings_enabled} onChange={event => setProfile({ ...profile, embeddings_enabled: event.target.checked })} />Use contextual embeddings in graph search</label>
      <p className="ai-settings-note">Allowed server bases: {profile.allowed_base_urls?.join(', ')}. Additional REST bases require AI_ALLOWED_BASE_URLS in .env.local. Saving settings does not download models.</p>
      <div className="ai-action-row">
        <IxButton disabled={busy} onClick={() => run(async () => { await save(); setMessage('Session AI settings saved.') })}>Save AI connection</IxButton>
        <IxButton variant="secondary" disabled={busy} onClick={() => run(async () => { await save(); const result = await aiRequest<{ models: string[] }>('models', 'POST', undefined, profile.request_timeout_seconds); setModels(result.models); setMessage(`${result.models.length} models discovered. Choose models and save again.`) })}>Save and discover models</IxButton>
        <IxButton variant="secondary" disabled={busy} onClick={() => run(async () => { await save(); const result = await aiRequest<{ chat: string; embedding_dimensions: number | null }>('test', 'POST', undefined, profile.request_timeout_seconds); setMessage(`Chat: ${result.chat}. Embedding dimensions: ${result.embedding_dimensions ?? 'disabled'}.`) })}>Save and test chat + embeddings</IxButton>
        <IxButton variant="tertiary" disabled={busy} onClick={() => run(async () => { await aiRequest('config', 'DELETE'); await load(); setKey(''); window.dispatchEvent(new Event('codetrace:ai-config')); setMessage('Session override removed; central defaults restored.') })}>Reset to central defaults</IxButton>
      </div>
    </>}
    {busy && <p role="status">Checking the configured REST service…</p>}
    {message && <p role="status">{message}</p>}
  </section>
}
