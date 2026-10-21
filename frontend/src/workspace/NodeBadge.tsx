import { classifyNode } from './nodeAppearance'
import { domainOf, type TraceNode } from './types'

export default function NodeBadge({ node, showDomain = true }: { node: TraceNode; showDomain?: boolean }) {
  const classification = classifyNode(node)
  return <span className="node-classification-badge"><span className="classification-swatch" style={{ backgroundColor: classification.color }} aria-hidden="true">{classification.glyph}</span>
    <span>{classification.label}{showDomain ? ` · ${domainOf(node)}` : ''}{node.properties.deleted ? ' · Deleted' : ''}</span></span>
}
