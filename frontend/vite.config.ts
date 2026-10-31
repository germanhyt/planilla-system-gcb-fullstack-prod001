/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [react(), tailwindcss(), VitePWA({ registerType: 'autoUpdate',
    // shell offline: precache de index.html/JS/CSS; navegaciones sin red sirven index.html (nunca /api)
    workbox: { navigateFallback: '/index.html', navigateFallbackDenylist: [/^\/api\//], globPatterns: ['**/*.{js,css,html,svg,png,ico,webmanifest,woff2}'] },
    manifest: { name: 'Planillas GCB', short_name: 'Planillas', start_url: '/', display: 'standalone', theme_color: '#1e0a2e', background_color: '#1e0a2e',
      icons: [
        { src: '/brand/pwa-192.png', sizes: '192x192', type: 'image/png' },
        { src: '/brand/pwa-512.png', sizes: '512x512', type: 'image/png' },
        { src: '/brand/pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ] } })],
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
  server: { proxy: { '/api': { target: 'http://localhost:8000', rewrite: p => p.replace(/^\/api/, '') } } },
})
