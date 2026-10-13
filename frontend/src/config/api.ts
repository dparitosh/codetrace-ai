// API paths are relative so the configured Vite proxy handles development/preview.
const config = __APP_CONFIG__
export const API_CONFIG = {
  BASE_URL: '',
  HEALTH: '/api/health',
  QUALITY: { LOCAL: '/api/v1/quality/local' },
  GRAPH: {
    CONFIGURATION: '/api/v1/graph/configuration',
    TRACE: '/api/v1/trace/materialize',
    LOCAL: '/api/v1/graph/local',
    LOCAL_ANALYZE: '/api/v1/graph/local/analyze',
    GITLAB: '/api/v1/graph/gitlab',
  },
  SECURITY: { LOCAL: '/api/v1/security/local' },
}
export const DIRECT_API_CONFIG = { BASE_URL: config.backendUrl, HEALTH: `${config.backendUrl}/health` }
export const CONFIG_INFO = { computed: config }
export default API_CONFIG
