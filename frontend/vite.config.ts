import react from '@vitejs/plugin-react'
import path from 'node:path'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaults = JSON.parse(readFileSync(path.join(root, 'config/defaults.json'), 'utf8'))

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, root, ''), ...process.env }
  const rawHost = env.HOST || defaults.HOST
  const host = rawHost.replace(/^\[([^\]]+)\]$/, '$1')
  const port = (name: string, fallback: number, raw = env[name]) => {
    const value = Number(raw ?? fallback)
    if (!Number.isInteger(value) || value < 1 || value > 65535) throw new Error(`${name} must be a port between 1 and 65535`)
    return value
  }
  const backendPort = port('BACKEND_PORT', defaults.BACKEND_PORT,
    process.env.BACKEND_PORT ?? process.env.PORT ?? env.BACKEND_PORT ?? env.PORT)
  const frontendPort = port('FRONTEND_PORT', defaults.FRONTEND_PORT)
  if (backendPort === frontendPort) throw new Error('BACKEND_PORT and FRONTEND_PORT must differ')
  const localHost = ['0.0.0.0', '::'].includes(host) ? '127.0.0.1' : host
  const browserHost = localHost.includes(':') ? `[${localHost}]` : localHost
  const backendUrl = `http://${browserHost}:${backendPort}`
  const controlTimeout = Number(env.CONTROL_REQUEST_TIMEOUT_SECONDS || defaults.CONTROL_REQUEST_TIMEOUT_SECONDS)
  if (!Number.isInteger(controlTimeout) || controlTimeout < 1) throw new Error('CONTROL_REQUEST_TIMEOUT_SECONDS must be a positive integer')
  const reviewPreviewItems = Number(env.REVIEW_PREVIEW_ITEMS || defaults.REVIEW_PREVIEW_ITEMS)
  if (!Number.isInteger(reviewPreviewItems) || reviewPreviewItems < 1) throw new Error('REVIEW_PREVIEW_ITEMS must be a positive integer')
  const proxy = { '/api': { target: backendUrl, changeOrigin: true } }
  return {
    envDir: root,
    // Node's built-in contract tests run separately; Vitest must not collect them.
    test: { include: ['src/**/*.test.{ts,tsx}'] },
    plugins: [react()],
    resolve: { alias: { '@': path.resolve(root, 'frontend/src') } },
    server: { host, port: frontendPort, strictPort: true, proxy },
    preview: { host, port: frontendPort, strictPort: true, proxy },
    build: { outDir: 'dist', sourcemap: true, rollupOptions: { output: { manualChunks: {
      graph: ['d3-force', 'd3-selection', 'd3-drag', 'd3-zoom'],
      session: [path.resolve(root, 'frontend/src/reviewSession.ts')],
      react: ['react', 'react-dom', 'react-dom/client'],
      icons: ['@siemens/ix-icons/icons'],
    } } } },
    // Only this explicit public projection is bundled into browser code.
    define: { __APP_CONFIG__: JSON.stringify({ host: browserHost, backendPort, frontendPort, backendUrl, controlTimeout, reviewPreviewItems }) },
  }
})
