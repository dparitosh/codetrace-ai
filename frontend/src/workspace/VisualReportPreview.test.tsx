import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import VisualReportPreview, { type VisualReport } from './VisualReportPreview'

const report:VisualReport={html:'<h1>Report</h1><script>untrusted()</script>',html_sha256:'hash',
  receipt:{snapshot_id:'snapshot',review_result_digest:'source',analysis_sha256:'analysis'}}

describe('in-app visual report',()=>{
  it('isolates report content and keeps pending export unavailable',()=>{
    const html=renderToStaticMarkup(<VisualReportPreview report={report} approved={false} exporting={false} onClose={()=>undefined} onExport={()=>undefined} />)
    expect(html).toContain('sandbox=""')
    expect(html).toContain('title="Visual code optimization assessment"')
    expect(html).toContain('srcDoc="&lt;h1&gt;')
    expect(html).not.toContain('<script>')
    expect(html).not.toContain('allow-scripts')
    expect(html).not.toContain('allow-same-origin')
    expect(html).toContain('Draft — source snapshot awaits approval')
    expect(html).toContain('disabled=""')
  })
  it('provides export inside the approved viewer',()=>{
    const html=renderToStaticMarkup(<VisualReportPreview report={report} approved={true} exporting={false} onClose={()=>undefined} onExport={()=>undefined} />)
    expect(html).toContain('Source snapshot approved')
    expect(html).toContain('Export approved report &amp; evidence')
    expect(html).not.toContain('disabled=""')
  })
})
