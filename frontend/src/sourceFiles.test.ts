import { describe, expect, it, vi } from 'vitest'
import { readSourceFiles, SourceConfiguration } from './sourceFiles'

const config: SourceConfiguration = {
  extensions: ['.py', '.js'], excludes: ['node_modules', '.git'], max_files: 2,
  max_payload_bytes: 50, max_file_bytes: 30, graph_preview_nodes: 100,
  graph_preview_edges: 220, max_trace_manifest_bytes: 1000, request_timeout_seconds: 120,
}
function file(path: string, content = '', size = new TextEncoder().encode(content).length) {
  return { name: path.split('/').pop(), webkitRelativePath: path, size, lastModified: 1,
    arrayBuffer: vi.fn(async () => new TextEncoder().encode(content).buffer) } as unknown as File
}

describe('folder source selection', () => {
  it('filters dependencies and unsupported assets before reading and applying limits', async () => {
    const excluded = Array.from({ length: 600 }, (_, i) => file(`project/node_modules/${i}.js`, '', 10000000))
    const asset = file('project/logo.png', '', 10000000)
    const notice = vi.fn()
    const result = await readSourceFiles([...excluded, asset, file('project/a.py', 'pass')], notice, config)
    expect(result.map(item => item.path)).toEqual(['project/a.py'])
    expect(notice).toHaveBeenCalledWith('Skipped 601 excluded or unsupported file(s); selected 1 source file(s).')
    expect(asset.arrayBuffer).not.toHaveBeenCalled()
    excluded.forEach(item => expect(item.arrayBuffer).not.toHaveBeenCalled())
  })
  it('rejects oversized source before allocating its contents', async () => {
    const large = file('a.py', '', 31)
    await expect(readSourceFiles([large], vi.fn(), config)).rejects.toThrow('per-file limit')
    expect(large.arrayBuffer).not.toHaveBeenCalled()
  })
  it('rejects too many supported files and aggregate byte overflow', async () => {
    await expect(readSourceFiles([file('a.py'), file('b.py'), file('c.py')], vi.fn(), config)).rejects.toThrow('at most 2')
    await expect(readSourceFiles([file('a.py', '', 30), file('b.py', '', 30)], vi.fn(), config)).rejects.toThrow('request limit')
  })
  it('rejects non-UTF-8 source instead of silently corrupting it', async () => {
    const invalid = file('a.py')
    invalid.arrayBuffer = async () => new Uint8Array([0xff]).buffer
    await expect(readSourceFiles([invalid], vi.fn(), config)).rejects.toThrow('UTF-8')
  })
  it('handles Windows paths and case-insensitive extensions', async () => {
    expect(await readSourceFiles([file('src\\a.PY', 'pass')], vi.fn(), config)).toHaveLength(1)
  })
})
