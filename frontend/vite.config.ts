import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
export default defineConfig({
  plugins: [react(), VitePWA({ registerType: 'autoUpdate', manifest: { name: 'Planillas GCB', short_name: 'Planillas', start_url: '/', display: 'standalone', theme_color: '#1e3a5f', icons: [] } })],
  server: { proxy: { '/api': { target: 'http://localhost:8000', rewrite: p => p.replace(/^\/api/, '') } } },
})
