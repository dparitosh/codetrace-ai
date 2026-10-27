import { useEffect, useState } from 'react'
import { IxButton } from '@siemens/ix-react'
import { aiRequest, useReviewSession } from '../reviewSession'

export interface AIProfile {
  enabled: boolean; base_url: string; model: string; embedding_model: string; key_header: string
  embeddings_enabled: boolean; key_configured: boolean; allowed_base_urls?: string[]; request_timeout_seconds?: number
  discovery_enabled?: boolean
  agents?: { id: string; label: string; description: string; tools: string[]; system_prompt: string }[]
  registered_tools?: { id: string; description: string }[]
  agent_configuration?: Record<string, { system_prompt: string; tools: string[] }>
  tool_configuration?: Record<string, { description: string }>
  companion_system_prompt?: string
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
    const { enabled, base_url, model, embedding_model, key_header, embeddings_enabled, discovery_enabled } = profile
    const result = await aiRequest<AIProfile>('config', 'PUT', { enabled, base_url, model, embedding_model, key_header, embeddings_enabled, discovery_enabled, api_key: key, keep_key: !clearKey,
      agent_configuration: profile.agent_configuration ?? {}, tool_configuration: profile.tool_configuration ?? {}, companion_system_prompt: profile.companion_system_prompt })
    setProfile(current => current ? { ...current, ...result } : result); setKey(''); setClearKey(false)
    window.dispatchEvent(new Event('codetrace:ai-config'))
  }
  return <section className="ai-settings" aria-label="Ollama AI configuration">
    <h2>AI connection</h2>
    <p>Configure this session’s models and agents. Credentials stay on the server; source catalogs and endpoint allowlists are managed in .env.local.</p>
    {!profile ? <IxButton disabled={busy} onClick={() => run(load)}>Start session and load AI settings</IxButton> : <>
      <label><input type="checkbox" checked={profile.enabled} onChange={event => setProfile({ ...profile, enabled: event.target.checked })} />Enable Ollama agent execution</label>
      <div className="ai-settings-grid">
        <label>Ollama REST URL<input aria-label="Ollama REST URL" value={profile.base_url} maxLength={2048} onChange={event => setProfile({ ...profile, base_url: event.target.value })} placeholder="Configured AI_BASE_URL" /></label>
        <label>Key header<select aria-label="Ollama key header" value={profile.key_header} onChange={event => setProfile({ ...profile, key_header: event.target.value })}><option>Authorization</option><option>api-key</option><option>Ocp-Apim-Subscription-Key</option></select></label>
        <label>API key<input aria-label="Ollama API key" type="password" autoComplete="off" value={key} maxLength={4096} onChange={event => setKey(event.target.value)} placeholder={profile.key_configured ? 'Saved key retained when blank' : 'Optional for local Ollama'} /></label>
        <label><input type="checkbox" checked={clearKey} onChange={event => setClearKey(event.target.checked)} />Remove saved key when saving</label>
        <label>Chat model<input aria-label="Ollama chat model" list="ollama-models" value={profile.model} maxLength={160} onChange={event => setProfile({ ...profile, model: event.target.value })} placeholder="Select an installed tool-capable model" /></label>
        <label>Embedding model<input aria-label="Ollama embedding model" list="ollama-models" value={profile.embedding_model} maxLength={160} onChange={event => setProfile({ ...profile, embedding_model: event.target.value })} placeholder="Configured AI_EMBEDDING_MODEL" /></label>
      </div>
      <datalist id="ollama-models">{models.map(model => <option key={model} value={model} />)}</datalist>
      <label><input type="checkbox" checked={profile.discovery_enabled ?? true} onChange={event => setProfile({ ...profile, discovery_enabled: event.target.checked })} />Discover installed models through /api/tags</label>
      <label><input type="checkbox" checked={profile.embeddings_enabled} onChange={event => setProfile({ ...profile, embeddings_enabled: event.target.checked })} />Use contextual embeddings in graph search</label>
      <h3>Agent instructions and tools</h3>
      <p>Edit each agent’s system prompt and enabled tools. Changes apply to subsequent runs in this session. The runtime still enforces read-only execution, evidence citations, validated parameters and execution budgets.</p>
      {profile.agents?.map(agent => {
        const current = profile.agent_configuration?.[agent.id] ?? { system_prompt: agent.system_prompt, tools: agent.tools }
        const update = (value: typeof current) => setProfile({ ...profile, agent_configuration: { ...profile.agent_configuration, [agent.id]: value } })
        return <details key={agent.id}><summary>{agent.label}</summary>
          <label>System prompt for {agent.label}<textarea aria-label={`${agent.label} system prompt`} rows={6} maxLength={12000} value={current.system_prompt} onChange={event => update({ ...current, system_prompt: event.target.value })} /></label>
          <fieldset><legend>Enabled tools for {agent.label}</legend>{profile.registered_tools?.map(tool => <label key={tool.id}>
            <input type="checkbox" checked={current.tools.includes(tool.id)} onChange={event => update({ ...current, tools: event.target.checked ? [...current.tools, tool.id] : current.tools.filter(name => name !== tool.id) })} />{tool.id}
          </label>)}</fieldset>
          {!current.tools.length && <p role="alert">Enable at least one tool before saving.</p>}
        </details>
      })}
      <details><summary>Tool instructions</summary><p>Configure the descriptions presented to the model. Tool implementations and parameter schemas remain registered server-side.</p>
        {profile.registered_tools?.map(tool => <label key={tool.id}>{tool.id}<textarea aria-label={`${tool.id} description`} rows={3} maxLength={2000} value={profile.tool_configuration?.[tool.id]?.description ?? tool.description} onChange={event => setProfile({ ...profile, tool_configuration: { ...profile.tool_configuration, [tool.id]: { description: event.target.value } } })} /></label>)}
      </details>
      <details><summary>Legacy companion instructions</summary><label>Companion system prompt<textarea aria-label="Companion system prompt" rows={6} maxLength={12000} value={profile.companion_system_prompt ?? ''} onChange={event => setProfile({ ...profile, companion_system_prompt: event.target.value })} /></label><p>The legacy companion has no executable tools.</p></details>
      <IxButton variant="tertiary" disabled={busy} onClick={() => run(async () => { await aiRequest('config', 'PUT', { enabled: profile.enabled, base_url: profile.base_url, model: profile.model, embedding_model: profile.embedding_model, key_header: profile.key_header, embeddings_enabled: profile.embeddings_enabled, discovery_enabled: profile.discovery_enabled, keep_key: true, agent_configuration: {}, tool_configuration: {} }); await load(); window.dispatchEvent(new Event('codetrace:ai-config')); setMessage('Agent prompts and tools restored to defaults. Connection and saved key retained.') })}>Restore agent and tool defaults</IxButton>
      <p className="ai-settings-note">Allowed server bases: {profile.allowed_base_urls?.join(', ')}. Additional REST bases require AI_ALLOWED_BASE_URLS in .env.local. Saving settings does not download models.</p>
      <div className="ai-action-row">
        <IxButton disabled={busy} onClick={() => run(async () => { await save(); setMessage('Session AI settings saved.') })}>Save AI connection</IxButton>
        <IxButton variant="secondary" disabled={busy || profile.discovery_enabled === false} onClick={() => run(async () => { await save(); const result = await aiRequest<{ models: string[] }>('models', 'POST', undefined, profile.request_timeout_seconds); setModels(result.models); setMessage(`${result.models.length} models discovered. Choose models and save again.`) })}>Save and discover models</IxButton>
        <IxButton variant="secondary" disabled={busy} onClick={() => run(async () => { await save(); const result = await aiRequest<{ chat: string; embedding_dimensions: number | null; discovery: { status: string }; warning: string }>('test', 'POST', undefined, profile.request_timeout_seconds); setMessage(`Discovery: ${result.discovery.status}. Chat: ${result.chat}. Embedding dimensions: ${result.embedding_dimensions ?? 'disabled'}. ${result.warning}`) })}>Save and test chat + embeddings</IxButton>
        <IxButton variant="tertiary" disabled={busy} onClick={() => run(async () => { await aiRequest('config', 'DELETE'); await load(); setKey(''); window.dispatchEvent(new Event('codetrace:ai-config')); setMessage('Session override removed; central defaults restored.') })}>Reset to central defaults</IxButton>
      </div>
    </>}
    {busy && <p role="status">Updating or checking AI configuration…</p>}
    {message && <p role="status">{message}</p>}
  </section>
}
