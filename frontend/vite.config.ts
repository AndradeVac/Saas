import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Local API used by the dev proxy; override with API_PROXY_TARGET if it runs elsewhere.
  const apiProxyTarget = loadEnv(mode, '.', '').API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Reachable as http://<slug>.localhost:5173 (browsers resolve *.localhost to this machine).
      proxy: {
        '/api': {
          target: apiProxyTarget,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
