import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Local API used by the dev proxy; override with API_PROXY_TARGET if it runs elsewhere.
  const apiProxyTarget = loadEnv(mode, '.', '').API_PROXY_TARGET || 'http://127.0.0.1:8010'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // All interfaces (IPv4 + IPv6): `127.0.0.1 <slug>.localhost` in /etc/hosts works (Safari), and phones on the
      // same Wi-Fi can open http://<this machine's IP>:5173/?tenant=<slug>.
      host: true,
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
