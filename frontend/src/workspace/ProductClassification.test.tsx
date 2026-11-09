import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import ProductClassification, { type Classification } from './ProductClassification'

const empty: Classification={status:'classification_requires_product_context',family:'',capabilities:[],features:[],
  coverage:{eligible_files:3,files_with_configured_evidence:0,functions_with_configured_evidence:0,files_requiring_classification:3,unmapped_features:[]},
  mappings:[],operations:[],lexical_proposals:[],configurations:[],feature_similarity:[],diagnostics:[],limitations:[]}

describe('product classification evidence',()=>{
  it('keeps classification gaps visible and permits opt-in taxonomy proposals without a predefined model',()=>{
    const html=renderToStaticMarkup(<ProductClassification data={empty} busy={false} stale={false} onAI={()=>undefined} onDraft={()=>undefined} onInspect={()=>undefined} />)
    expect(html).toContain('3 files require classification')
    expect(html).toContain('provisional AI taxonomy')
    expect(html).toContain('Request AI classification proposals')
    expect(html).not.toContain('disabled')
  })
  it('labels model taxonomy as proposed and prevents accepting stale evidence',()=>{
    const data={...empty,ai_review:{status:'proposals_require_review',features:[{id:'f',label:'<script>unsafe</script>',description:'Tentative',capability_id:'c',citation_ids:['E1']}]}}
    const html=renderToStaticMarkup(<ProductClassification data={data} busy={false} stale={true} onAI={()=>undefined} onDraft={()=>undefined} onInspect={()=>undefined} />)
    expect(html).toContain('Proposed feature:')
    expect(html).toContain('&lt;script&gt;unsafe&lt;/script&gt;')
    expect(html).not.toContain('<script>')
    expect(html).toContain('disabled')
    expect(html).toContain('Add proposed feature to draft context')
  })
})
