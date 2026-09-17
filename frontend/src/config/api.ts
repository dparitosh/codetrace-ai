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

  // Quality endpoints
  QUALITY: {
    LOCAL: '/api/v1/quality/local',
  },

  // Graph endpoints
  GRAPH: {
    ENHANCED_TRACEABILITY: '/api/v1/graph/enhanced-traceability',
    LOCAL: '/api/v1/graph/local',
    LOCAL_ANALYZE: '/api/v1/graph/local/analyze',
    GITLAB: '/api/v1/graph/gitlab',
  },

  // Security endpoints
  SECURITY: {
    LOCAL: '/api/v1/security/local',
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
