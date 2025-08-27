import { useEffect, useState } from 'react'
import './App.css'
import AnalysisPage from './components/AnalysisPage'
import GraphPage from './components/GraphPage'
import QualityPage from './components/QualityPage'
import SecurityPage from './components/SecurityPage'
import { API_CONFIG, CONFIG_INFO } from './config/api'

// Icons (simplified SVG components)
const AnalysisIcon = () => (
  <svg className="w-8 h-8 text-blue-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
)

const QualityIcon = () => (
  <svg className="w-8 h-8 text-green-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const GraphIcon = () => (
  <svg className="w-8 h-8 text-purple-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
)

const SecurityIcon = () => (
  <svg className="w-8 h-8 text-red-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
)

function App() {
  const [backendStatus, setBackendStatus] = useState({
    api: 'loading',
    database: 'loading', 
    github: 'loading'
  })
  const [activeDemo, setActiveDemo] = useState('analysis')
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [currentRepositoryUrl, setCurrentRepositoryUrl] = useState('')

  // Simulate backend status check
  useEffect(() => {
    const checkBackendStatus = async () => {
      try {
        const response = await fetch(API_CONFIG.HEALTH)
        if (response.ok) {
          const data = await response.json()
          setBackendStatus({
            api: 'online',
            database: data.components?.database === 'connected' ? 'online' : 'dev-mode',
            github: data.components?.github === 'connected' ? 'online' : 'ready'
          })
        }
      } catch (error) {
        console.log('Backend status check - using mock data for demo')
        // Simulate successful connection for demo
        setTimeout(() => {
          setBackendStatus({
            api: 'online',
            database: 'dev-mode',
            github: 'ready'
          })
        }, 1000)
      }
    }
    
    checkBackendStatus()
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'bg-green-500'
      case 'dev-mode': return 'bg-yellow-500'
      case 'ready': return 'bg-blue-500'
      case 'loading': return 'bg-gray-400 animate-pulse'
      default: return 'bg-red-500'
    }
  }

  const getStatusText = (component: string, status: string) => {
    if (status === 'loading') return `${component}: Checking...`
    
    const statusMap: Record<string, Record<string, string>> = {
      api: { online: 'API Server: Running', offline: 'API Server: Offline' },
      database: { 
        online: 'Database: Connected', 
        'dev-mode': 'Database: Development Mode',
        offline: 'Database: Offline' 
      },
      github: { 
        online: 'GitHub: Connected', 
        ready: 'GitHub Integration: Ready',
        offline: 'GitHub: Offline' 
      }
    }
    
    return statusMap[component]?.[status] || `${component}: ${status}`
  }

  const handleFeatureClick = (feature: string) => {
    setActiveDemo(feature)
    setCurrentPage(feature)
    // Navigate to feature page
    console.log(`Navigating to ${feature} feature`)
  }

  const handleNavigation = (page: string) => {
    setCurrentPage(page)
  }

  const handleBackToDashboard = () => {
    setCurrentPage('dashboard')
  }

  const handleNavigateToQuality = (repositoryUrl: string) => {
    setCurrentRepositoryUrl(repositoryUrl)
    setCurrentPage('quality')
  }

  const handleNavigateToGraph = (repositoryUrl: string) => {
    setCurrentRepositoryUrl(repositoryUrl)
    setCurrentPage('graph')
  }

  // Render different pages based on current page
  if (currentPage === 'analysis') {
    return (
      <AnalysisPage 
        onBack={handleBackToDashboard}
        onNavigateToQuality={handleNavigateToQuality}
        onNavigateToGraph={handleNavigateToGraph}
      />
    )
  }

  if (currentPage === 'quality') {
    return <QualityPage onBack={handleBackToDashboard} initialRepositoryUrl={currentRepositoryUrl} />
  }

  if (currentPage === 'graph') {
    return <GraphPage onBack={handleBackToDashboard} initialRepositoryUrl={currentRepositoryUrl} />
  }

  if (currentPage === 'security') {
    return <SecurityPage />
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-gray-900">
                CodeTrace AI
              </h1>
              <span className="ml-3 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded">
                v1.0.0
              </span>
            </div>
            <nav className="flex space-x-8">
              <button onClick={() => handleNavigation('dashboard')} className="text-gray-600 hover:text-gray-900">Dashboard</button>
              <button onClick={() => handleNavigation('analysis')} className="text-gray-600 hover:text-gray-900">Analysis</button>
              <button onClick={() => handleNavigation('quality')} className="text-gray-600 hover:text-gray-900">Quality</button>
              <button onClick={() => handleNavigation('graph')} className="text-gray-600 hover:text-gray-900">Graphs</button>
              <button onClick={() => handleNavigation('security')} className="text-gray-600 hover:text-gray-900">Security</button>
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            GitHub Repository Analysis Platform
          </h2>
          <p className="text-lg text-gray-600 mb-8">
            Advanced code analysis, dependency visualization, and quality assessment
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mt-12">
            <div className={`bg-white p-6 rounded-lg shadow-lg transition-all duration-200 hover:shadow-xl cursor-pointer border-2 ${
              activeDemo === 'analysis' ? 'border-blue-500' : 'border-transparent'
            }`} onClick={() => handleFeatureClick('analysis')}>
              <div className="flex flex-col items-center text-center">
                <AnalysisIcon />
                <h3 className="text-xl font-semibold text-gray-900 mb-3">
                  Repository Analysis
                </h3>
                <p className="text-gray-600 mb-4">
                  Deep analysis of code structure, dependencies, and patterns
                </p>
                <button 
                  onClick={() => handleFeatureClick('analysis')}
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors duration-200 font-medium"
                >
                  Start Analysis
                </button>
              </div>
            </div>

            <div className={`bg-white p-6 rounded-lg shadow-lg transition-all duration-200 hover:shadow-xl cursor-pointer border-2 ${
              activeDemo === 'quality' ? 'border-green-500' : 'border-transparent'
            }`} onClick={() => handleFeatureClick('quality')}>
              <div className="flex flex-col items-center text-center">
                <QualityIcon />
                <h3 className="text-xl font-semibold text-gray-900 mb-3">
                  Quality Assessment
                </h3>
                <p className="text-gray-600 mb-4">
                  Code quality metrics, security scans, and recommendations
                </p>
                <button 
                  onClick={() => handleFeatureClick('quality')}
                  className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition-colors duration-200 font-medium"
                >
                  Check Quality
                </button>
              </div>
            </div>

            <div className={`bg-white p-6 rounded-lg shadow-lg transition-all duration-200 hover:shadow-xl cursor-pointer border-2 ${
              activeDemo === 'graph' ? 'border-purple-500' : 'border-transparent'
            }`} onClick={() => handleFeatureClick('graph')}>
              <div className="flex flex-col items-center text-center">
                <GraphIcon />
                <h3 className="text-xl font-semibold text-gray-900 mb-3">
                  Dependency Graph
                </h3>
                <p className="text-gray-600 mb-4">
                  Interactive visualization of code dependencies and relationships
                </p>
                <button 
                  onClick={() => handleFeatureClick('graph')}
                  className="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 transition-colors duration-200 font-medium"
                >
                  View Graph
                </button>
              </div>
            </div>

            <div className={`bg-white p-6 rounded-lg shadow-lg transition-all duration-200 hover:shadow-xl cursor-pointer border-2 ${
              activeDemo === 'security' ? 'border-red-500' : 'border-transparent'
            }`} onClick={() => handleFeatureClick('security')}>
              <div className="flex flex-col items-center text-center">
                <SecurityIcon />
                <h3 className="text-xl font-semibold text-gray-900 mb-3">
                  Security & Compliance
                </h3>
                <p className="text-gray-600 mb-4">
                  CVSS vulnerability scanning, SBOM generation, and SPDX compliance
                </p>
                <button 
                  onClick={() => handleFeatureClick('security')}
                  className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition-colors duration-200 font-medium"
                >
                  Security Scan
                </button>
              </div>
            </div>
          </div>

          <div className="mt-12 bg-white p-8 rounded-lg shadow-lg">
            <h3 className="text-2xl font-bold text-gray-900 mb-6 text-center">
              System Status
            </h3>
            <div className="flex flex-wrap items-center justify-center gap-6">
              <div className="flex items-center">
                <div className={`w-3 h-3 rounded-full mr-3 ${getStatusColor(backendStatus.api)}`}></div>
                <span className="text-gray-700 font-medium">{getStatusText('api', backendStatus.api)}</span>
              </div>
              <div className="flex items-center">
                <div className={`w-3 h-3 rounded-full mr-3 ${getStatusColor(backendStatus.database)}`}></div>
                <span className="text-gray-700 font-medium">{getStatusText('database', backendStatus.database)}</span>
              </div>
              <div className="flex items-center">
                <div className={`w-3 h-3 rounded-full mr-3 ${getStatusColor(backendStatus.github)}`}></div>
                <span className="text-gray-700 font-medium">{getStatusText('github', backendStatus.github)}</span>
              </div>
            </div>
            <div className="mt-6 text-center">
              <p className="text-sm text-gray-500">
                Backend API: <code className="bg-gray-100 px-2 py-1 rounded text-xs font-mono">{CONFIG_INFO.computed.backendUrl}</code>
              </p>
              <p className="text-sm text-gray-500 mt-1">
                Frontend UI: <code className="bg-gray-100 px-2 py-1 rounded text-xs font-mono">http://{CONFIG_INFO.computed.host}:{CONFIG_INFO.computed.frontendPort}</code>
              </p>
            </div>
          </div>

          {/* Demo Feature Preview */}
          <div className="mt-12 bg-gradient-to-r from-blue-50 to-purple-50 p-8 rounded-lg border">
            <h3 className="text-xl font-bold text-gray-900 mb-4 text-center">
              🚀 Selected Feature: {activeDemo.charAt(0).toUpperCase() + activeDemo.slice(1)}
            </h3>
            <p className="text-center text-gray-600">
              Click on the feature cards above to see different sections highlighted. 
              In the full application, this would navigate to dedicated feature pages.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
