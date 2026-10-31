import { test, type Page } from '@playwright/test'
import { login } from '../tests/helpers'

// S8 paso 5: capturas dark/light de pantallas clave -> shots-out/s8-<pantalla>-<tema>.png
const ir = async (page: Page, menu: string) => { await page.locator('nav').getByRole('button', { name: menu, exact: true }).click(); await page.waitForTimeout(1200) }
for (const theme of ['dark', 'light']) {
  test(`s8 admin ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.addInitScript(t => localStorage.setItem('gcb-theme', t), theme)
    await login(page, 'admin@demo.gcb.pe'); await page.waitForTimeout(2500)
    await page.screenshot({ path: `shots-out/s8-dashboard-${theme}.png` })
    await page.getByRole('button', { name: 'Ver notificaciones' }).click(); await page.waitForTimeout(900)
    await page.screenshot({ path: `shots-out/s8-notificaciones-popover-${theme}.png` })
    await page.keyboard.press('Escape')
    await ir(page, 'Excepciones'); await page.screenshot({ path: `shots-out/s8-bandeja-${theme}.png` })
    await ir(page, 'Reportes'); await page.screenshot({ path: `shots-out/s8-reportes-${theme}.png` })
    await ir(page, 'Configuración'); await page.screenshot({ path: `shots-out/s8-configuracion-${theme}.png` })
    await ir(page, 'Trabajadores'); await page.getByRole('combobox').filter({ hasText: '50' }).last().selectOption('10').catch(() => {})
    await page.waitForTimeout(900); await page.screenshot({ path: `shots-out/s8-trabajadores-paginado-${theme}.png` })
  })
  test(`s8 marcar mobile ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addInitScript(t => localStorage.setItem('gcb-theme', t), theme)
    await login(page, 'trabajador@demo.gcb.pe'); await page.waitForTimeout(1200)
    await page.screenshot({ path: `shots-out/s8-marcar-mobile-${theme}.png` })
  })
}
