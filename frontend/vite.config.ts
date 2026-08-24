import react from '@vitejs/plugin-react'
import path from 'path'
import { defineConfig, loadEnv } from 'vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables
  const env = loadEnv(mode, process.cwd(), '')

  // Get configuration from environment with fallbacks - NO HARDCODING
  const host = env.VITE_HOST || env.HOST || 'localhost'
  const backendPort = env.VITE_BACKEND_PORT || env.BACKEND_PORT || '8009'
  const frontendPort = env.VITE_FRONTEND_PORT || env.FRONTEND_PORT || '3001'

  console.log(`🔧 Vite Configuration:`)
  console.log(`   Frontend: http://${host}:${frontendPort}`)
  console.log(`   Backend Proxy: http://${host}:${backendPort}`)

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: parseInt(frontendPort),
      host: true,
      strictPort: false, // Allow fallback to other ports
      proxy: {
        '/api': {
          target: `http://${host}:${backendPort}`,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
    define: {
      // Make environment variables available to the app at build time
      'import.meta.env.VITE_HOST': JSON.stringify(host),
      'import.meta.env.VITE_BACKEND_PORT': JSON.stringify(backendPort),
      'import.meta.env.VITE_FRONTEND_PORT': JSON.stringify(frontendPort),
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(`http://${host}:${backendPort}`),
    }
  }
})
