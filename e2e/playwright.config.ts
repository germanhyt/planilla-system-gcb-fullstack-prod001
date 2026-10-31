import { defineConfig } from '@playwright/test'

// E2E contra el stack ya levantado (web :8080). En contenedor: BASE_URL=http://host.docker.internal:8080
export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: process.env.BASE_URL || 'http://localhost:8080', locale: 'es-PE', timezoneId: 'America/Lima',
         trace: 'retain-on-failure' },
})
