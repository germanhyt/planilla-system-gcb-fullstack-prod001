import { test, type Page } from '@playwright/test'
import { login } from '../tests/helpers'

// S8 paso 6: Justificaciones y HE programadas paginadas en servidor (dark) -> shots-out/s8p6-*.png
// Siembra datos demo vía API (duplicados se ignoran) para que haya varias páginas.
const ir = async (page: Page, menu: string) => { await page.locator('nav').getByRole('button', { name: menu, exact: true }).click(); await page.waitForTimeout(1500) }
test('s8p6 justificaciones y HE paginadas dark', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.addInitScript(() => localStorage.setItem('gcb-theme', 'dark'))
  await login(page, 'admin@demo.gcb.pe'); await page.waitForTimeout(1000)
  const r = await page.evaluate(async () => {
    const h = { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('token')}` }
    const ts: any[] = await (await fetch('/api/trabajadores', { headers: h })).json()
    const lista = (Array.isArray(ts) ? ts : (ts as any).items).slice(0, 8)
    const mot = ['permiso', 'salud', 'otro']; let ok = 0
    const hoy = new Date()
    for (let i = 0; i < 24; i++) {
      const t = lista[i % lista.length]
      const pas = new Date(hoy.getTime() - (2 + i) * 864e5).toISOString().slice(0, 10)
      const fut = new Date(hoy.getTime() + (1 + (i % 12)) * 864e5).toISOString().slice(0, 10)
      const a = await fetch('/api/justificaciones', { method: 'POST', headers: h, body: JSON.stringify({ trabajador_id: t.id, dia: pas, motivo: mot[i % 3], descripcion: `Demo paginación ${i + 1}` }) })
      const b = await fetch('/api/he-programadas', { method: 'POST', headers: h, body: JSON.stringify({ trabajador_id: t.id, dia: fut, horas: 1 + (i % 3), motivo: `Inventario ${i + 1}` }) })
      ok += (a.ok ? 1 : 0) + (b.ok ? 1 : 0)
    }
    return ok
  })
  console.log('sembrados', r)
  await ir(page, 'Justificaciones')
  await page.getByRole('button', { name: 'Todas' }).click(); await page.waitForTimeout(1200)
  await page.screenshot({ path: 'shots-out/s8p6-justificaciones-dark.png', fullPage: true })
  await ir(page, 'Horas extra programadas')
  await page.screenshot({ path: 'shots-out/s8p6-he-programadas-dark.png', fullPage: true })
})
