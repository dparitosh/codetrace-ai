import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { ReactNode } from 'react'
import AnalysisPage from './AnalysisPage'

const state = vi.hoisted(() => ({ graph: { nodes: [] as any[], edges: [], metadata: {} } }))
vi.mock('../workspace/workspaceContext', () => ({ useWorkspaceGraph: () => state }))
vi.mock('./SourceAnalysisPage', () => ({ default: ({ children }: { children: ReactNode }) => <section>{children}</section> }))

describe('native source analysis coverage', () => {
  it('shows friendly C-family languages, partial parsing and a safe missing-parser warning', () => {
    state.graph.nodes = [
      { id: 'c', type: 'file', label: 'app.c', properties: { language: 'c', parse_status: 'parsed', extraction: 'tree_sitter' } },
      { id: 'cpp', type: 'file', label: 'app.cpp', properties: { language: 'cpp', parse_status: 'partial', extraction: 'tree_sitter' } },
      { id: 'cs', type: 'file', label: 'App.cs', properties: { language: 'csharp', parse_status: 'heuristic', parser_warning: '<script>missing grammar</script>' } },
    ]
    const html = renderToStaticMarkup(<AnalysisPage />)
    for (const label of ['C++', 'C#', 'Parsed syntax', 'Recovered syntax errors', 'Heuristic extraction', 'not compiler or runtime verification']) expect(html).toContain(label)
    expect(html).toContain('&lt;script&gt;missing grammar&lt;/script&gt;')
    expect(html).not.toContain('<script>missing grammar</script>')
  })
})
