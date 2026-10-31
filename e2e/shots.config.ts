import { defineConfig } from '@playwright/test'
// Capturas visuales del shell (no forman parte de la suite): npx playwright test -c shots.config.ts
export default defineConfig({ testDir: './shots', timeout: 60_000, workers: 1, reporter: [['list']],
  use: { baseURL: process.env.BASE_URL || 'http://localhost:8080', locale: 'es-PE', timezoneId: 'America/Lima' } })
