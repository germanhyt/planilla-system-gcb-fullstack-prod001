import { test } from '@playwright/test'
import { login } from '../tests/helpers'

const casos = [
  { n: 'desktop', vp: { width: 1440, height: 900 }, user: 'rrhh@demo.gcb.pe' },
  { n: 'mobile', vp: { width: 390, height: 844 }, user: 'rrhh@demo.gcb.pe' },
  { n: 'mobile-trabajador', vp: { width: 390, height: 844 }, user: 'trabajador@demo.gcb.pe' },
]
for (const c of casos) for (const theme of ['dark', 'light']) {
  test(`shell ${c.n} ${theme}`, async ({ page }) => {
    await page.setViewportSize(c.vp)
    await page.addInitScript(t => localStorage.setItem('gcb-theme', t), theme)
    await login(page, c.user)
    await page.waitForTimeout(600)
    await page.screenshot({ path: `shots-out/shell-${c.n}-${theme}.png` })
    if (c.n === 'mobile') {
      await page.getByRole('button', { name: 'Abrir men\u00fa' }).click(); await page.waitForTimeout(400)
      await page.screenshot({ path: `shots-out/shell-mobile-drawer-${theme}.png` })
    }
    if (c.n === 'desktop' && theme === 'dark') {
      await page.getByRole('button', { name: 'Contraer men\u00fa' }).click(); await page.waitForTimeout(300)
      await page.screenshot({ path: `shots-out/shell-desktop-collapsed-dark.png` })
      await page.getByRole('button', { name: 'Expandir men\u00fa' }).click()
    }
  })
}
test('login dark', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 }); await page.goto('/')
  await page.screenshot({ path: 'shots-out/login-dark.png' })
})
