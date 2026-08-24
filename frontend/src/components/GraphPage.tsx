import { useEffect, useState } from 'react'
import { API_CONFIG } from '../config/api'
import { BarChart3, Download, ExternalLink, FileText, GitBranch, Link2, Network, Palette, Zap } from 'lucide-react'

interface GraphPageProps {
  onBack: () => void
  initialRepositoryUrl?: string
}

function GraphCanvas({ graphData }: { graphData: any }) {
  const nodes = (graphData?.nodes || []).slice(0, 80)
  const edges = graphData?.edges || graphData?.links || []
  const width = 760
  const height = 360
  const positions = new Map(nodes.map((node: any, index: number) => {
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2
    return [String(node.id ?? node.label ?? node.name ?? index), {
      x: width / 2 + Math.cos(angle) * 300,
      y: height / 2 + Math.sin(angle) * 140,
    }]
  }))
  const resolvePosition = (value: any) => positions.get(String(value?.id ?? value?.label ?? value?.name ?? value))

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[640px] h-[360px]" role="img" aria-label="Dependency graph preview">
        <defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#94a3b8" /></marker></defs>
        <g stroke="#cbd5e1" strokeWidth="1.5" markerEnd="url(#graph-arrow)">
          {edges.slice(0, 180).map((edge: any, index: number) => {
            const source = resolvePosition(edge.source)
            const target = resolvePosition(edge.target)
            return source && target ? <line key={`${index}-${edge.source}-${edge.target}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} /> : null
          })}
        </g>
        {nodes.map((node: any, index: number) => {
          const position = positions.get(String(node.id ?? node.label ?? node.name ?? index))
          if (!position) return null
          const type = node.type || node.kind || 'node'
          const fill = type === 'function' ? '#dcfce7' : type === 'class' ? '#ede9fe' : type === 'package' ? '#fef3c7' : '#dbeafe'
          const stroke = type === 'function' ? '#16a34a' : type === 'class' ? '#7c3aed' : type === 'package' ? '#d97706' : '#2563eb'
          return <g key={String(node.id ?? node.label ?? index)}><circle cx={position.x} cy={position.y} r="18" fill={fill} stroke={stroke} strokeWidth="2" /><text x={position.x} y={position.y + 32} textAnchor="middle" fontSize="10" fill="#334155">{String(node.label ?? node.name ?? node.id ?? type).slice(0, 24)}</text></g>
        })}
      </svg>
      <div className="flex flex-wrap gap-3 border-t border-gray-200 px-4 py-2 text-xs text-gray-600">
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-blue-600" />file/module</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-violet-600" />class</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-green-600" />function</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-amber-600" />package</span>
      </div>
    </div>
  )
}

export default function GraphPage({ onBack, initialRepositoryUrl }: GraphPageProps) {
  const [repositoryUrl, setRepositoryUrl] = useState(initialRepositoryUrl || '')
  const [isGenerating, setIsGenerating] = useState(false)
  const [graphData, setGraphData] = useState<any>(null)
  const [enhancedGraphData, setEnhancedGraphData] = useState<any>(null)
  const [error, setError] = useState('')
  const [layoutType, setLayoutType] = useState('force-directed')
  const [showEnhancedGraph, setShowEnhancedGraph] = useState(false)
  const [localFiles, setLocalFiles] = useState<File[]>([])

  // Load enhanced traceability graph on component mount
  useEffect(() => {
    loadEnhancedTraceabilityGraph()
  }, [])

  const loadEnhancedTraceabilityGraph = async () => {
    try {
      const response = await fetch(API_CONFIG.GRAPH.ENHANCED_TRACEABILITY)
      if (response.ok) {
        const result = await response.json()
        if (result.success) {
          setEnhancedGraphData(result.graph_data)
        }
      }
    } catch (err) {
      console.log('Enhanced graph not available:', err)
    }
  }

  const handleGenerateGraph = async () => {
    if (!repositoryUrl.trim() && localFiles.length === 0) {
      setError('Select a local folder or enter a repository URL')
      return
    }

    const githubUrlPattern = /^https:\/\/github\.com\/[\w\-\.]+\/[\w\-\.]+(\/(tree|blob)\/[\w\-\.\/]+)?\/?$/
    if (!localFiles.length && !githubUrlPattern.test(repositoryUrl.trim())) {
      setError('Please enter a valid GitHub repository URL')
      return
    }

    setIsGenerating(true)
    setError('')
    setGraphData(null)

    try {
      const response = await fetch(`/api/v1/graph/${localFiles.length ? 'local' : 'dependency'}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(localFiles.length
          ? { files: await Promise.all(localFiles.map(async (file) => ({
              path: file.webkitRelativePath || file.name,
              content: await file.text(),
            }))) }
          : { repository_url: repositoryUrl.trim(), layout: layoutType,
              filters: { node_types: ['file', 'function', 'class'], min_connections: 1 }, format: 'd3' })
      })

      if (!response.ok) {
        throw new Error(`Graph generation failed: ${response.statusText}`)
      }

      const result = await response.json()
      setGraphData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Graph generation failed')
    } finally {
      setIsGenerating(false)
    }
  }

  const getNodeTypeColor = (type: string) => {
    switch (type) {
      case 'file': return 'bg-blue-100 text-blue-800'
      case 'function': return 'bg-green-100 text-green-800'
      case 'class': return 'bg-purple-100 text-purple-800'
      case 'module': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getEdgeTypeColor = (type: string) => {
    switch (type) {
      case 'imports': return 'text-blue-600'
      case 'calls': return 'text-green-600'
      case 'inherits': return 'text-purple-600'
      case 'uses': return 'text-yellow-600'
      default: return 'text-gray-600'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <button
            onClick={onBack}
            className="flex items-center text-purple-600 hover:text-purple-800 mb-4"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-900">Dependency Graph</h1>
          <p className="text-gray-600 mt-2">Interactive visualization of code dependencies and relationships</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Graph Generation</h2>
              
              <div className="space-y-4">
                <div>
                  <label htmlFor="repository-url" className="block text-sm font-medium text-gray-700 mb-2">
                    GitHub Repository URL
                  </label>
                  <input
                    type="url"
                    id="repository-url"
                    value={repositoryUrl}
                    onChange={(e) => setRepositoryUrl(e.target.value)}
                    placeholder="https://github.com/owner/repository"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    disabled={isGenerating}
                  />
                </div>

                <div className="border-t pt-4">
                  <label htmlFor="local-folder" className="block text-sm font-medium text-gray-700 mb-2">
                    Or select a local source folder
                  </label>
                  <input
                    id="local-folder"
                    type="file"
                    multiple
                    // @ts-expect-error webkitdirectory is supported by Chromium-based browsers
                    webkitdirectory="true"
                    onChange={(event) => setLocalFiles(Array.from(event.target.files || []))}
                    disabled={isGenerating}
                    className="w-full text-sm text-gray-600"
                  />
                  {localFiles.length > 0 && (
                    <p className="mt-2 text-sm text-green-700">{localFiles.length} source files selected</p>
                  )}
                </div>

                <div>
                  <label htmlFor="layout-type" className="block text-sm font-medium text-gray-700 mb-2">
                    Layout Algorithm
                  </label>
                  <select
                    id="layout-type"
                    value={layoutType}
                    onChange={(e) => setLayoutType(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    disabled={isGenerating}
                  >
                    <option value="force-directed">Force Directed</option>
                    <option value="hierarchical">Hierarchical</option>
                    <option value="circular">Circular</option>
                    <option value="grid">Grid</option>
                  </select>
                </div>

                {error && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-red-800 text-sm">{error}</p>
                  </div>
                )}

                <button
                  onClick={handleGenerateGraph}
                  disabled={isGenerating}
                  className="w-full bg-purple-600 text-white py-3 px-4 rounded-lg hover:bg-purple-700 disabled:bg-purple-400 disabled:cursor-not-allowed transition-colors duration-200 font-medium"
                >
                  {isGenerating ? (
                    <div className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Generating Graph...
                    </div>
                  ) : (
                    'Generate Graph'
                  )}
                </button>
              </div>
            </div>

            {/* Graph Stats */}
            {graphData && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Graph Statistics</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Nodes:</span>
                    <span className="font-medium">{graphData.metadata?.total_nodes || graphData.nodes?.length || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Edges:</span>
                    <span className="font-medium">{graphData.metadata?.total_edges || graphData.edges?.length || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Layout:</span>
                    <span className="font-medium capitalize">{graphData.metadata?.layout_algorithm || layoutType}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Complexity:</span>
                    <span className="font-medium">{graphData.metadata?.complexity_score || 'N/A'}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Graph Visualization */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-lg p-6" style={{ minHeight: '600px' }}>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  {showEnhancedGraph ? 'Enhanced Traceability Graph' : 'Dependency Visualization'}
                </h2>
                {enhancedGraphData && (
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setShowEnhancedGraph(false)}
                      className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                        !showEnhancedGraph 
                          ? 'bg-purple-600 text-white' 
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      Generated Graph
                    </button>
                    <button
                      onClick={() => setShowEnhancedGraph(true)}
                      className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                        showEnhancedGraph 
                          ? 'bg-purple-600 text-white' 
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      E2E Trace Graph
                    </button>
                  </div>
                )}
              </div>
              
              {showEnhancedGraph && enhancedGraphData ? (
                <div className="space-y-4">
                  {/* Enhanced Graph Preview */}
                  <div className="bg-gradient-to-br from-purple-900 to-blue-900 rounded-lg p-6 text-white">
                    <div className="text-center mb-4">
                      <h3 className="text-2xl font-bold mb-2 flex items-center justify-center gap-2"><GitBranch aria-hidden="true" /> GraphTrace Hierarchical Traceability</h3>
                      <p className="text-purple-200">Interactive expandable graph with impact analysis</p>
                    </div>
                    
                    {/* Graph Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                      <div className="bg-white bg-opacity-10 rounded-lg p-4 text-center">
                        <div className="text-2xl font-bold">{enhancedGraphData.nodes?.length || 0}</div>
                        <div className="text-sm text-purple-200">Total Nodes</div>
                      </div>
                      <div className="bg-white bg-opacity-10 rounded-lg p-4 text-center">
                        <div className="text-2xl font-bold">{enhancedGraphData.links?.length || 0}</div>
                        <div className="text-sm text-purple-200">Connections</div>
                      </div>
                      <div className="bg-white bg-opacity-10 rounded-lg p-4 text-center">
                        <div className="text-2xl font-bold">{enhancedGraphData.hierarchical ? 'Yes' : 'No'}</div>
                        <div className="text-sm text-purple-200">Hierarchical</div>
                      </div>
                    </div>

                    {/* Graph Description */}
                    <div className="bg-white bg-opacity-10 rounded-lg p-4 mb-6">
                      <h4 className="font-semibold mb-2 flex items-center gap-2"><FileText aria-hidden="true" /> Analysis Description</h4>
                      <p className="text-sm text-purple-100">
                        {enhancedGraphData.graph?.description || 'Enhanced hierarchical traceability graph with interactive exploration capabilities'}
                      </p>
                    </div>

                    {/* Interactive Controls */}
                    <div className="flex flex-wrap gap-2 justify-center">
                      <button 
                        onClick={() => window.open('/analysis/ENHANCED_TRACEABILITY_GRAPH/enhanced-traceability-graph.html', '_blank')}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                      >
                        <ExternalLink className="inline-block mr-2 h-4 w-4" aria-hidden="true" /> Open Interactive Graph
                      </button>
                      <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                        <BarChart3 className="inline-block mr-2 h-4 w-4" aria-hidden="true" /> View Analysis Report
                      </button>
                      <button className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                        <Download className="inline-block mr-2 h-4 w-4" aria-hidden="true" /> Export Data
                      </button>
                    </div>
                  </div>

                  {/* Node Types Overview */}
                  {enhancedGraphData.nodes && (
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-3">Node Types Overview</h4>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {Object.entries(
                          enhancedGraphData.nodes.reduce((acc: any, node: any) => {
                            acc[node.type] = (acc[node.type] || 0) + 1
                            return acc
                          }, {})
                        ).map(([type, count]) => (
                          <div key={type} className="bg-white p-2 rounded border text-center">
                            <div className="text-lg font-bold text-purple-600">{count as number}</div>
                            <div className="text-xs text-gray-600 capitalize">{type.replace('_', ' ')}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <>
              {!graphData && !isGenerating && (
                <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                  <div className="text-center">
                    <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <p className="text-gray-500 text-lg">Generate a graph to see visualization</p>
                    <p className="text-gray-400 text-sm mt-2">Enter a repository URL and click "Generate Graph"</p>
                  </div>
                </div>
              )}

              {isGenerating && (
                <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg">
                  <div className="text-center">
                    <svg className="animate-spin w-16 h-16 text-purple-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <p className="text-gray-700 text-lg">Generating dependency graph...</p>
                    <p className="text-gray-500 text-sm mt-2">This may take a few moments</p>
                  </div>
                </div>
              )}

              {graphData && (
                <div className="space-y-4">
                  {/* Graph Preview */}
                  <div className="bg-gray-50 rounded-lg p-4 min-h-96 border">
                    <GraphCanvas graphData={graphData} />
                  </div>

                  {/* Node List */}
                  {graphData.nodes && graphData.nodes.length > 0 && (
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-3">Graph Nodes ({graphData.nodes.length})</h4>
                      <div className="max-h-48 overflow-y-auto space-y-2">
                        {graphData.nodes.slice(0, 10).map((node: any, index: number) => (
                          <div key={index} className="flex items-center justify-between bg-white p-2 rounded border">
                            <div className="flex items-center">
                              <span className={`px-2 py-1 text-xs font-medium rounded mr-3 ${getNodeTypeColor(node.type)}`}>
                                {node.type}
                              </span>
                              <span className="text-sm font-medium text-gray-900">{node.label}</span>
                            </div>
                            <span className="text-xs text-gray-500">Size: {node.size || 1}</span>
                          </div>
                        ))}
                        {graphData.nodes.length > 10 && (
                          <p className="text-center text-gray-500 text-sm py-2">
                            ... and {graphData.nodes.length - 10} more nodes
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Edge List */}
                  {graphData.edges && graphData.edges.length > 0 && (
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-3">Graph Edges ({graphData.edges.length})</h4>
                      <div className="max-h-48 overflow-y-auto space-y-2">
                        {graphData.edges.slice(0, 10).map((edge: any, index: number) => (
                          <div key={index} className="flex items-center justify-between bg-white p-2 rounded border">
                            <div className="flex items-center text-sm">
                              <span className="font-medium text-gray-900">{edge.source}</span>
                              <span className={`mx-2 ${getEdgeTypeColor(edge.type)}`}>
                                → {edge.type} →
                              </span>
                              <span className="font-medium text-gray-900">{edge.target}</span>
                            </div>
                            <span className="text-xs text-gray-500">Weight: {edge.weight || 1}</span>
                          </div>
                        ))}
                        {graphData.edges.length > 10 && (
                          <p className="text-center text-gray-500 text-sm py-2">
                            ... and {graphData.edges.length - 10} more edges
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
                </>
              )}
            </div>
          </div>
        </div>

        <div className="mt-8 bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Graph Visualization Features</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center p-4">
              <Link2 className="h-8 w-8 mx-auto mb-2 text-blue-600" aria-hidden="true" />
              <h3 className="font-medium text-gray-900">Dependencies</h3>
              <p className="text-sm text-gray-600">Visualize code dependencies and imports</p>
            </div>
            <div className="text-center p-4">
              <Zap className="h-8 w-8 mx-auto mb-2 text-yellow-600" aria-hidden="true" />
              <h3 className="font-medium text-gray-900">Interactive</h3>
              <p className="text-sm text-gray-600">Click, zoom, and explore graph elements</p>
            </div>
            <div className="text-center p-4">
              <Palette className="h-8 w-8 mx-auto mb-2 text-purple-600" aria-hidden="true" />
              <h3 className="font-medium text-gray-900">Multiple Layouts</h3>
              <p className="text-sm text-gray-600">Force-directed, hierarchical, and more</p>
            </div>
            <div className="text-center p-4">
              <Network className="h-8 w-8 mx-auto mb-2 text-green-600" aria-hidden="true" />
              <h3 className="font-medium text-gray-900">Export Options</h3>
              <p className="text-sm text-gray-600">PNG, SVG, PDF, and JSON formats</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
