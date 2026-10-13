import { API_CONFIG } from './config/api'
import { requestJson } from './reviewSession'

export interface SourceConfiguration {
  extensions: string[]
  excludes: string[]
  request_timeout_seconds: number
  max_files: number
  max_payload_bytes: number
  max_file_bytes: number
  graph_preview_nodes: number
  graph_preview_edges: number
  max_trace_manifest_bytes: number
}

export async function loadSourceConfiguration(): Promise<SourceConfiguration> {
  return requestJson(API_CONFIG.GRAPH.CONFIGURATION)
}

export async function readSourceFiles(
  files: File[],
  onNotice: (notice: string) => void,
  config?: SourceConfiguration,
) {
  const settings = config || await loadSourceConfiguration()
  const selected = files.filter(file => {
    const parts = (file.webkitRelativePath || file.name).replace(/\\/g, '/').split('/')
    const name = parts[parts.length - 1]
    const extension = name.includes('.') ? name.slice(name.lastIndexOf('.')).toLowerCase() : ''
    return !parts.some(part => settings.excludes.includes(part)) && settings.extensions.includes(extension)
  })
  const skipped = files.length - selected.length
  onNotice(skipped ? `Skipped ${skipped} excluded or unsupported file(s); selected ${selected.length} source file(s).` : '')
  if (!selected.length) throw new Error('No supported source files were selected.')
  if (selected.length > settings.max_files) throw new Error(`Select at most ${settings.max_files} source files.`)
  const oversized = selected.find(file => file.size > settings.max_file_bytes)
  if (oversized) throw new Error(`${oversized.webkitRelativePath || oversized.name} exceeds the ${settings.max_file_bytes}-byte per-file limit.`)
  if (selected.reduce((sum, file) => sum + file.size, 0) > settings.max_payload_bytes) {
    throw new Error(`Selected source exceeds the ${settings.max_payload_bytes}-byte request limit.`)
  }
  // Validate before reading; sequential decoding keeps peak memory bounded.
  const result = []
  let bytes = 0
  for (const file of selected) {
    let content: string
    try {
      content = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer())
    } catch {
      throw new Error(`Cannot read ${file.webkitRelativePath || file.name} as UTF-8 source.`)
    }
    const size = new TextEncoder().encode(content).length
    bytes += size
    if (size > settings.max_file_bytes || bytes > settings.max_payload_bytes) throw new Error('Decoded source exceeds the configured byte limits.')
    result.push({ path: file.webkitRelativePath || file.name, content, size, last_modified: file.lastModified })
  }
  return result
}
