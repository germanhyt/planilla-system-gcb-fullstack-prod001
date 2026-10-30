import { expect, Page } from '@playwright/test'

export const PASSWORD = process.env.E2E_PASSWORD || 'Cambiar123!'

export async function login(page: Page, email: string) {
  await page.goto('/')
  await page.getByPlaceholder('Correo').fill(email)
  await page.getByPlaceholder('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page.getByRole('heading', { name: 'Mi perfil' })).toBeVisible()
}

export async function abrir(page: Page, menu: string, titulo: string | RegExp) {
  await page.locator('nav').getByRole('button', { name: menu, exact: true }).click()
  await expect(page.getByRole('heading', { name: titulo })).toBeVisible()
}
