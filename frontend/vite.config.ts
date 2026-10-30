/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
export default defineConfig({
  plugins: [react(), VitePWA({ registerType: 'autoUpdate',
    // shell offline: precache de index.html/JS/CSS; navegaciones sin red sirven index.html (nunca /api)
    workbox: { navigateFallback: '/index.html', navigateFallbackDenylist: [/^\/api\//], globPatterns: ['**/*.{js,css,html,svg,png,ico,webmanifest}'] },
    manifest: { name: 'Planillas GCB', short_name: 'Planillas', start_url: '/', display: 'standalone', theme_color: '#1e3a5f', icons: [] } })],
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
  server: { proxy: { '/api': { target: 'http://localhost:8000', rewrite: p => p.replace(/^\/api/, '') } } },
})
