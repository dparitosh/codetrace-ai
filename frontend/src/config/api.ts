// Configuration file for API endpoints - NO HARDCODED URLS
// All URLs are constructed from environment variables with safe fallbacks

// Get configuration from environment variables with proper type checking
const getConfig = () => {
  // Safe environment variable access with fallbacks
  const host = import.meta.env?.VITE_HOST || 'localhost';
  const backendPort = import.meta.env?.VITE_BACKEND_PORT || '8009';
  const frontendPort = import.meta.env?.VITE_FRONTEND_PORT || '3001';
  const backendUrl = import.meta.env?.VITE_BACKEND_URL || `http://${host}:${backendPort}`;

  return {
    host,
    backendPort,
    frontendPort,
    backendUrl,
  };
};

const config = getConfig();

export const API_CONFIG = {
  // Use relative URLs for API calls to leverage Vite proxy
  BASE_URL: '',

  // Health endpoint
  HEALTH: '/api/health',

  // GitHub API endpoints
  GITHUB: {
    ANALYZE: '/api/v1/github/analyze',
    ANALYSIS_STATUS: (id: string) => `/api/v1/github/analysis/status/${id}`,
    ANALYSIS_RESULTS: (id: string) => `/api/v1/github/analysis/results/${id}`,
  },

  // Quality endpoints
  QUALITY: {
    ASSESS: '/api/v1/quality/assess',
  },

  // Graph endpoints
  GRAPH: {
    ENHANCED_TRACEABILITY: '/api/v1/graph/enhanced-traceability',
    DEPENDENCY: '/api/v1/graph/dependency',
  },

  // Security endpoints
  SECURITY: {
    COMPLIANCE: (repositoryUrl: string) => `/api/v1/security/compliance/dashboard?repository_url=${encodeURIComponent(repositoryUrl)}`,
    CVSS_SCAN: '/api/v1/security/cvss/scan',
    SBOM_GENERATE: '/api/v1/security/sbom/generate',
  },

  // MCP endpoints - DYNAMIC, NO HARDCODING
  MCP: {
    LIVE_ANALYSIS_WS: `ws://${config.host}:${config.backendPort}/api/v1/mcp/frontend/live-analysis`,
  }
}

// Fallback URLs for direct API calls (when proxy is not available) - DYNAMIC
export const DIRECT_API_CONFIG = {
  BASE_URL: config.backendUrl,
  HEALTH: `${config.backendUrl}/health`,
}

// Configuration info for debugging
export const CONFIG_INFO = {
  environment: {
    VITE_HOST: import.meta.env.VITE_HOST || 'not set',
    VITE_BACKEND_PORT: import.meta.env.VITE_BACKEND_PORT || 'not set',
    VITE_FRONTEND_PORT: import.meta.env.VITE_FRONTEND_PORT || 'not set',
    VITE_BACKEND_URL: import.meta.env.VITE_BACKEND_URL || 'not set',
  },
  computed: config,
}

export default API_CONFIG
