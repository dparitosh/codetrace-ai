import { useRef } from 'react'

type EvidenceTab = 'overview' | 'graph' | 'table'
export default function EvidenceTabs({ value, onChange, overview }: { value: EvidenceTab; onChange: (value: EvidenceTab) => void; overview?: string }) {
  const buttons = useRef(new Map<EvidenceTab, HTMLButtonElement>())
  const tabs: { id: EvidenceTab; label: string }[] = [...(overview ? [{ id: 'overview' as const, label: overview }] : []), { id: 'graph', label: 'Graph' }, { id: 'table', label: 'Data grid' }]
  return <div role="tablist" aria-label="Page evidence" className="evidence-tabs">{tabs.map((tab, index) => <button key={tab.id} ref={element => { if (element) buttons.current.set(tab.id, element); else buttons.current.delete(tab.id) }}
    role="tab" id={`evidence-${tab.id}-tab`} aria-controls={`evidence-${tab.id}-panel`} aria-selected={value === tab.id} tabIndex={value === tab.id ? 0 : -1}
    onClick={() => onChange(tab.id)} onKeyDown={event => {
      const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null
      if (next === null) return
      event.preventDefault(); onChange(tabs[next].id); buttons.current.get(tabs[next].id)?.focus()
    }}>{tab.label}</button>)}</div>
}
