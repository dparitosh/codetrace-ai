import { useState } from 'react'
import { BarChart3, Clock3, FileText, Lightbulb, Search } from 'lucide-react'
import { API_CONFIG } from '../config/api'

interface QualityPageProps {
  onBack: () => void
  initialRepositoryUrl?: string
}

export default function QualityPage({ onBack, initialRepositoryUrl }: QualityPageProps) {
  const [repositoryUrl, setRepositoryUrl] = useState(initialRepositoryUrl || '')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [qualityResult, setQualityResult] = useState<any>(null)
  const [error, setError] = useState('')

  const handleQualityCheck = async () => {
    if (!repositoryUrl.trim()) {
      setError('Please enter a repository URL')
      return
    }

    const githubUrlPattern = /^https:\/\/github\.com\/[\w\-\.]+\/[\w\-\.]+(\/(tree|blob)\/[\w\-\.\/]+)?\/?$/
    if (!githubUrlPattern.test(repositoryUrl.trim())) {
      setError('Please enter a valid GitHub repository URL')
      return
    }

    setIsAnalyzing(true)
    setError('')
    setQualityResult(null)

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

      // First analyze the repository, then get quality metrics
      const analysisResponse = await fetch(API_CONFIG.GITHUB.ANALYZE, {
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

      if (!analysisResponse.ok) {
        throw new Error(`Analysis failed: ${analysisResponse.statusText}`)
      }

      const analysisResult = await analysisResponse.json()

      // Get quality metrics
      const qualityResponse = await fetch(API_CONFIG.QUALITY.ASSESS, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repository: repository,
          include_metrics: true,
          rules: null
        })
      })

      if (!qualityResponse.ok) {
        throw new Error(`Quality assessment failed: ${qualityResponse.statusText}`)
      }

      const result = await qualityResponse.json()
      setQualityResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Quality assessment failed')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-50'
    if (score >= 60) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <button
            onClick={onBack}
            className="flex items-center text-green-600 hover:text-green-800 mb-4"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-900">Quality Assessment</h1>
          <p className="text-gray-600 mt-2">Comprehensive code quality analysis, metrics, and recommendations</p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Quality Check</h2>
          
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
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                disabled={isAnalyzing}
              />
            </div>

            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-800 text-sm">{error}</p>
              </div>
            )}

            <button
              onClick={handleQualityCheck}
              disabled={isAnalyzing}
              className="w-full bg-green-600 text-white py-3 px-4 rounded-lg hover:bg-green-700 disabled:bg-green-400 disabled:cursor-not-allowed transition-colors duration-200 font-medium"
            >
              {isAnalyzing ? (
                <div className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Analyzing Quality...
                </div>
              ) : (
                'Check Quality'
              )}
            </button>
          </div>
        </div>

        {qualityResult && (
          <div className="space-y-6">
            {/* Overall Score */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Overall Quality Score</h2>
              <div className="flex items-center justify-center">
                <div className={`text-6xl font-bold p-8 rounded-full ${getScoreColor(qualityResult.overall_score || 0)}`}>
                  {(qualityResult.overall_score || 0).toFixed(1)}
                  <span className="text-2xl ml-2">{qualityResult.grade || 'N/A'}</span>
                </div>
              </div>
              <p className="text-center text-gray-600 mt-4">
                Quality score based on complexity, maintainability, and best practices
              </p>
            </div>

            {/* Detailed Metrics */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Quality Breakdown</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {(qualityResult.metrics || []).map((metric: any, index: number) => (
                  <div key={index} className={`p-4 rounded-lg ${
                    metric.status === 'pass' ? 'bg-green-50' :
                    metric.status === 'warning' ? 'bg-yellow-50' : 'bg-red-50'
                  }`}>
                    <h3 className={`text-sm font-medium ${
                      metric.status === 'pass' ? 'text-green-800' :
                      metric.status === 'warning' ? 'text-yellow-800' : 'text-red-800'
                    }`}>{metric.name}</h3>
                    <p className={`text-2xl font-bold ${
                      metric.status === 'pass' ? 'text-green-900' :
                      metric.status === 'warning' ? 'text-yellow-900' : 'text-red-900'
                    }`}>
                      {metric.name === 'Security Issues' ? `${metric.value}` : `${(metric.value || 0).toFixed(1)}${metric.name && metric.name.includes('Coverage') ? '%' : ''}`}
                    </p>
                    <div className={`w-full rounded-full h-2 mt-2 ${
                      metric.status === 'pass' ? 'bg-green-200' :
                      metric.status === 'warning' ? 'bg-yellow-200' : 'bg-red-200'
                    }`}>
                      <div 
                        className={`h-2 rounded-full transition-all duration-500 ${
                          metric.status === 'pass' ? 'bg-green-600' :
                          metric.status === 'warning' ? 'bg-yellow-600' : 'bg-red-600'
                        }`}
                        style={{ width: `${Math.min(metric.value || 0, 100)}%` }}
                      ></div>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">{metric.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Recommendations */}
            {qualityResult.recommendations && qualityResult.recommendations.length > 0 && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Recommendations</h2>
                <div className="space-y-3">
                  {qualityResult.recommendations.map((recommendation: string, index: number) => (
                    <div key={index} className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg">
                      <Lightbulb className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" aria-hidden="true" />
                      <p className="text-gray-700 text-sm">{recommendation}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Issues */}
            {qualityResult.issues && qualityResult.issues.length > 0 && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Quality Issues</h2>
                <div className="space-y-3">
                  {qualityResult.issues.map((issue: any, index: number) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center mb-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded ${
                              issue.severity === 'error' ? 'bg-red-100 text-red-800' :
                              issue.severity === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-blue-100 text-blue-800'
                            }`}>
                              {issue.severity}
                            </span>
                            <span className="ml-2 text-sm font-medium text-gray-900">{issue.type}</span>
                          </div>
                          <p className="text-gray-700 mb-2">{issue.description}</p>
                          <p className="text-sm text-gray-500">
                            <span className="inline-flex items-center gap-1"><FileText className="h-4 w-4" aria-hidden="true" /> {issue.file_path} {issue.line_number && `(Line ${issue.line_number})`}</span>
                          </p>
                          {issue.recommendation && (
                            <div className="mt-3 p-3 bg-blue-50 rounded border-l-4 border-blue-400">
                              <p className="text-sm text-blue-800">
                                <Lightbulb className="inline-block mr-1 h-4 w-4 text-yellow-600" aria-hidden="true" /> <strong>Recommendation:</strong> {issue.recommendation}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {qualityResult.recommendations && qualityResult.recommendations.length > 0 && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Improvement Recommendations</h2>
                <div className="space-y-3">
                  {qualityResult.recommendations.map((rec: any, index: number) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center mb-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded ${
                              rec.priority === 'high' ? 'bg-red-100 text-red-800' :
                              rec.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {rec.priority} priority
                            </span>
                            <span className="ml-2 text-sm font-medium text-gray-900">{rec.category}</span>
                          </div>
                          <p className="text-gray-700 mb-2">{rec.description}</p>
                          {rec.estimated_effort && (
                            <p className="text-sm text-gray-500">
                              <span className="inline-flex items-center gap-1"><Clock3 className="h-4 w-4" aria-hidden="true" /> Estimated effort: {rec.estimated_effort}</span>
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-8 bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Quality Assessment Features</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-4">
              <Search className="h-8 w-8 mx-auto mb-2 text-blue-600" aria-hidden="true" />
              <h3 className="font-medium text-gray-900">Code Analysis</h3>
              <p className="text-sm text-gray-600">Deep analysis of code complexity and structure</p>
            </div>
            <div className="text-center p-4">
              <BarChart3 className="h-8 w-8 mx-auto mb-2 text-blue-600" aria-hidden="true" />
              <h3 className="font-medium text-gray-900">Quality Metrics</h3>
              <p className="text-sm text-gray-600">Comprehensive quality scoring and metrics</p>
            </div>
            <div className="text-center p-4">
              <Lightbulb className="h-8 w-8 mx-auto mb-2 text-yellow-600" aria-hidden="true" />
              <h3 className="font-medium text-gray-900">Recommendations</h3>
              <p className="text-sm text-gray-600">Actionable suggestions for improvement</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
