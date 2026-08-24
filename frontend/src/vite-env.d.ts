/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_HOST: string
  readonly VITE_BACKEND_PORT: string
  readonly VITE_FRONTEND_PORT: string
  readonly VITE_BACKEND_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
