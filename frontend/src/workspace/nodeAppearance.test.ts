import { describe, expect, it } from 'vitest'
import { classifyNode, nodeFill, nodeGlyphColor, nodeLegend } from './nodeAppearance'
import { domainColors, domainOf, type TraceNode } from './types'

const node = (type: string, properties = {}): TraceNode => ({ id: type, type, label: type, properties })
describe('graph node classification', () => {
  it('distinguishes code artifact classes within the same domain', () => {
    const types = ['repository', 'package', 'file', 'module', 'class', 'function', 'method', 'variable', 'symbol']
    expect(new Set(types.map(type => nodeFill(node(type)))).size).toBe(types.length)
    for (const type of types) {
      expect(domainOf(node(type))).toBe('CODE')
      expect(classifyNode(node(type)).glyph).not.toBe('?')
      expect(nodeFill(node(type), 'domain')).toBe(domainColors.CODE)
    }
  })
  it('infers lifecycle classifications when older data omits its domain', () => {
    const expected = { requirement: 'RM', requirement_collection: 'RM', test_result: 'QM', architecture: 'AM', build: 'CI', sbom_component: 'SBOM', external_resource: 'EXTERNAL' }
    for (const [type, domain] of Object.entries(expected)) {
      expect(domainOf(node(type))).toBe(domain)
      expect(nodeFill(node(type), 'domain')).toBe(domainColors[domain])
    }
    expect(domainOf(node('requirement', { domain: 'trs' }))).toBe('TRS')
  })
  it('preserves unknown type labels and falls back for unregistered domains', () => {
    const custom = node('custom_resource', { domain: 'CUSTOM' })
    expect(classifyNode(custom).label).toBe('custom resource')
    expect(classifyNode(custom).glyph).toBe('?')
    expect(nodeFill(custom, 'domain')).toBe(domainColors.EXTERNAL)
  })
  it('counts the displayed nodes rather than the full snapshot', () => {
    const nodes = [node('file'), { ...node('file'), id: 'file-two' }, node('class'), node('test')]
    expect(nodeLegend(nodes, 'classification').find(entry => entry.key === 'file')?.count).toBe(2)
    expect(nodeLegend(nodes, 'domain').find(entry => entry.key === 'CODE')?.count).toBe(3)
    expect(nodeLegend(nodes, 'domain').find(entry => entry.key === 'QM')?.count).toBe(1)
  })
  it('keeps classification colors stable for deleted resources and chooses readable glyphs', () => {
    expect(nodeFill(node('requirement', { deleted: true }))).toBe(nodeFill(node('requirement')))
    const luminance = (hex: string) => {
      const rgb = hex.slice(1).match(/../g)!.map(value => parseInt(value, 16) / 255)
      const values = rgb.map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
      return values[0] * .2126 + values[1] * .7152 + values[2] * .0722
    }
    for (const type of ['file', 'class', 'function', 'requirement', 'test_result', 'sbom_component', 'external_resource']) {
      for (const mode of ['classification', 'domain'] as const) {
        const background = luminance(nodeFill(node(type), mode)), foreground = luminance(nodeGlyphColor(node(type), mode))
        expect((Math.max(background, foreground) + .05) / (Math.min(background, foreground) + .05)).toBeGreaterThanOrEqual(4.5)
      }
    }
  })
})
