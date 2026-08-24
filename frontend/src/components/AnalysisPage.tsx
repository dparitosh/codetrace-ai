import { useEffect, useState } from 'react'
import { DIRECT_API_CONFIG } from '../config/api'

interface AnalysisPageProps {
  onBack: () => void
  onNavigateToQuality?: (repositoryUrl: string) => void
  onNavigateToGraph?: (repositoryUrl: string) => void
}

export default function AnalysisPage({ onBack, onNavigateToQuality, onNavigateToGraph }: AnalysisPageProps) {
  const [repositoryUrl, setRepositoryUrl] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [analysisStatus, setAnalysisStatus] = useState<any>(null)
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])

  // Poll for analysis status updates
  const startStatusPolling = (analysisId: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${DIRECT_API_CONFIG.BASE_URL}/api/v1/github/analysis/status/${analysisId}`)
        if (response.ok) {
          const status = await response.json()
          setAnalysisStatus(status)
          
          // If analysis is completed, get the full results
          if (status.status === 'completed') {
            clearInterval(interval)
            setPollingInterval(null)
            
            try {
              const resultsResponse = await fetch(`${DIRECT_API_CONFIG.BASE_URL}/api/v1/github/analysis/results/${analysisId}`)
              if (resultsResponse.ok) {
                const results = await resultsResponse.json()
                setAnalysisResult(results)
              }
            } catch (err) {
              console.error('Error fetching analysis results:', err)
            }
            
            setIsAnalyzing(false)
          }
        }
      } catch (err) {
        console.error('Error polling analysis status:', err)
      }
    }, 2000) // Poll every 2 seconds
    
    setPollingInterval(interval)
  }

  const handleAnalysis = async () => {
    if (!repositoryUrl.trim()) {
      setError('Please enter a repository URL')
      return
    }

    // Validate GitHub URL format - support branch/path URLs
    const githubUrlPattern = /^https:\/\/github\.com\/[\w\-\.]+\/[\w\-\.]+(\/(tree|blob)\/[\w\-\.\/]+)?\/?$/
    if (!githubUrlPattern.test(repositoryUrl.trim())) {
      setError('Please enter a valid GitHub repository URL (e.g., https://github.com/owner/repo)')
      return
    }

    setIsAnalyzing(true)
    setError('')
    setAnalysisResult(null)

    try {
      // Extract owner/repo from GitHub URL
      const extractRepoFromUrl = (url: string) => {
        const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)/);
        if (match) {
          return `${match[1]}/${match[2]}`;
        }
        throw new Error('Invalid GitHub URL format');
      };

      const repository = extractRepoFromUrl(repositoryUrl.trim());

      const response = await fetch(`${DIRECT_API_CONFIG.BASE_URL}/api/v1/github/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repository: repository,
          options: {
            include_quality: true,
            include_security: true,
            include_dependencies: true,
            include_graph: true,
            auto_fix: false,
            create_pr: false
          }
        })
      })

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`)
      }

      const result = await response.json()
      setAnalysisResult(result)
      
      // Start polling for status updates if we got an analysis_id
      if (result.analysis_id && result.status === 'processing') {
        setAnalysisStatus(result)
        startStatusPolling(result.analysis_id)
      } else {
        setIsAnalyzing(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <button
            onClick={onBack}
            className="flex items-center text-blue-600 hover:text-blue-800 mb-4"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-900">Repository Analysis</h1>
          <p className="text-gray-600 mt-2">Analyze GitHub repositories for code structure, dependencies, and patterns</p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Start New Analysis</h2>
          
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
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isAnalyzing}
              />
            </div>

            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-800 text-sm">{error}</p>
              </div>
            )}

            <button
              onClick={handleAnalysis}
              disabled={isAnalyzing}
              className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition-colors duration-200 font-medium"
            >
              {isAnalyzing ? (
                <div className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Analyzing Repository...
                </div>
              ) : (
                'Start Analysis'
              )}
            </button>
          </div>
        </div>

        {(analysisResult || analysisStatus) && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Analysis Results</h2>
            
            {/* Show current status if still processing */}
            {analysisStatus && analysisStatus.status === 'processing' && (
              <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-lg font-medium text-blue-900">Analysis in Progress</h3>
                  <span className="text-sm text-blue-700">{analysisStatus.progress}%</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2 mb-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500" 
                    style={{ width: `${analysisStatus.progress}%` }}
                  ></div>
                </div>
                <p className="text-sm text-blue-700">{analysisStatus.message}</p>
              </div>
            )}
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-blue-800">Analysis ID</h3>
                <p className="text-lg font-bold text-blue-900 break-all">
                  {analysisResult?.analysis_id || analysisStatus?.analysis_id}
                </p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-green-800">Status</h3>
                <p className="text-xl font-bold text-green-900">
                  {analysisStatus?.status || analysisResult?.status}
                </p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-purple-800">Repository</h3>
                <p className="text-sm font-bold text-purple-900">
                  {analysisResult?.repository || analysisStatus?.repository || '/'}
                </p>
              </div>
              <div className="bg-yellow-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-yellow-800">Branch</h3>
                <p className="text-xl font-bold text-yellow-900">
                  {analysisResult?.branch || 'main'}
                </p>
              </div>
            </div>

            {/* Show completed results */}
            {analysisResult && analysisResult.results && (
              <div className="space-y-4 mb-6">
                <h3 className="text-lg font-semibold text-gray-900">Analysis Summary</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-medium text-gray-900 mb-2">Code Statistics</h4>
                    <div className="space-y-1 text-sm">
                      <div>Total Files: <span className="font-semibold">{analysisResult.results.summary?.total_files}</span></div>
                      <div>Total Lines: <span className="font-semibold">{analysisResult.results.summary?.total_lines}</span></div>
                      <div>Languages: <span className="font-semibold">{analysisResult.results.summary?.languages?.join(', ')}</span></div>
                    </div>
                  </div>
                  
                  <div className="bg-green-50 p-4 rounded-lg">
                    <h4 className="font-medium text-gray-900 mb-2">Quality Scores</h4>
                    <div className="space-y-1 text-sm">
                      <div>Overall: <span className="font-semibold">{analysisResult.results.quality?.overall_score}</span></div>
                      <div>Complexity: <span className="font-semibold">{analysisResult.results.quality?.complexity_score}</span></div>
                      <div>Maintainability: <span className="font-semibold">{analysisResult.results.quality?.maintainability_score}</span></div>
                    </div>
                  </div>
                  
                  <div className="bg-red-50 p-4 rounded-lg">
                    <h4 className="font-medium text-gray-900 mb-2">Security</h4>
                    <div className="space-y-1 text-sm">
                      <div>Vulnerabilities: <span className="font-semibold">{analysisResult.results.security?.vulnerabilities_found}</span></div>
                      <div>Security Score: <span className="font-semibold">{analysisResult.results.summary?.security_score}</span></div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Raw response for debugging */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="text-lg font-medium text-gray-900 mb-2">Raw Response</h3>
              <pre className="text-sm text-gray-700 overflow-x-auto max-h-64 overflow-y-auto">
                {JSON.stringify(analysisResult || analysisStatus, null, 2)}
              </pre>
            </div>

            <div className="mt-6 flex space-x-4">
              <button 
                onClick={() => onNavigateToQuality?.(repositoryUrl)}
                className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition-colors duration-200"
                disabled={!analysisResult || analysisResult.status !== 'completed'}
              >
                View Quality Report
              </button>
              <button 
                onClick={() => onNavigateToGraph?.(repositoryUrl)}
                className="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 transition-colors duration-200"
                disabled={!analysisResult || analysisResult.status !== 'completed'}
              >
                View Dependency Graph
              </button>
            </div>
          </div>
        )}

        <div className="mt-8 bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Example Repositories</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                 onClick={() => setRepositoryUrl('https://github.com/fastapi/fastapi')}>
              <h3 className="font-medium text-gray-900">FastAPI</h3>
              <p className="text-sm text-gray-600">Modern, fast web framework for building APIs</p>
              <p className="text-xs text-blue-600 mt-1">fastapi/fastapi</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                 onClick={() => setRepositoryUrl('https://github.com/microsoft/vscode')}>
              <h3 className="font-medium text-gray-900">VS Code</h3>
              <p className="text-sm text-gray-600">Source code for Visual Studio Code</p>
              <p className="text-xs text-blue-600 mt-1">microsoft/vscode</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
