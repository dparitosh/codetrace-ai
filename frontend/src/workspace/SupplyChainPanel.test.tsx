import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { TraceGraph } from './types'
import SupplyChainPanel from './SupplyChainPanel'

vi.mock('./ForceGraphCanvas', () => ({ default: () => <div>Dependency canvas</div> }))
afterEach(() => vi.unstubAllGlobals())

describe('incomplete supply-chain evidence', () => {
  it.each([false, true])('exposes unresolved dependencies when resolved components exist: %s', hasComponents => {
    vi.stubGlobal('window', { matchMedia: () => ({ matches: false }) })
    const graph: TraceGraph = {
      nodes: [{ id: 'app', label: 'App', type: 'repository', properties: {} },
        ...(hasComponents ? [{ id: 'a', label: 'A', type: 'sbom_component', properties: {} }] : [])],
      edges: [], metadata: { sbom: { unresolved_dependencies: [
        { name: '<script>bad</script>', kind: 'required', source: '(application)', lockfile: 'package-lock.json' },
      ] } },
    }
    const html = renderToStaticMarkup(<SupplyChainPanel graph={graph} review={null} />)
    expect(html).toContain('Dependency lineage is incomplete: 1 declared dependencies')
    expect(html).toContain('Unresolved dependency evidence')
    expect(html).toContain('&lt;script&gt;bad&lt;/script&gt;')
    expect(html).not.toContain('<script>bad</script>')
    if (!hasComponents) expect(html).toContain('No resolved SBOM components')
  })
})
