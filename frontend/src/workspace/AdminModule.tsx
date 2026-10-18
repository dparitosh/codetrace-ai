import AISettings from './AISettings'

export default function AdminModule() {
  return <section aria-label="Administration module"><span className="eyebrow">ADMINISTRATION</span><h2>AI and agent configuration</h2><p>Manage session AI credentials, agent system prompts and registered tools. Central source catalogs and endpoint allowlists remain in .env.local. This local workspace does not enforce account-based administrator roles.</p><AISettings /></section>
}
