import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import ProductLinePanel from './ProductLinePanel'

vi.mock('../reviewSession', () => ({ workspaceRequest: vi.fn() }))

describe('product-line optimization controls', () => {
  it('explains the need for source evidence before projections', () => {
    const html=renderToStaticMarkup(<ProductLinePanel review={null} catalog={null} onSelect={() => undefined} />)
    expect(html).toContain('configurable source folder')
    expect(html).not.toContain('Export approved')
  })
  it('keeps unapproved export unavailable and names assumptions explicitly', () => {
    const review={id:'r',status:'pending',result_digest:'digest',kind:'graph',revision:0,created_at:'',audit:[]} as any
    const html=renderToStaticMarkup(<ProductLinePanel review={review} catalog={null} onSelect={() => undefined} />)
    expect(html).toContain('Open visual report')
    expect(html).toContain('Planning adoption (%)')
    expect(html).toContain('Retained wrapper lines')
    expect(html).toContain('structural directory groups')
    expect(html).toContain('Export approved report &amp; evidence')
    expect(html).toContain('approve the exact source snapshot')
    expect(html).toContain('disabled')
  })
})
