/**
 * E2E de humo del piloto (solo lectura: no crea marcas, no cierra periodos -> seguro contra dev).
 * Usuarios de la semilla demo: {trabajador,jefe,rrhh,admin}@demo.gcb.pe
 */
import { expect, test } from '@playwright/test'
import { abrir, login } from './helpers'

test('api /health responde ok a traves del proxy web', async ({ request }) => {
  const r = await request.get('/api/health')
  expect(r.ok()).toBeTruthy()
})

test('login invalido muestra error', async ({ page }) => {
  await page.goto('/')
  await page.getByPlaceholder('Correo').fill('nadie@demo.gcb.pe')
  await page.getByPlaceholder('Contraseña').fill('mala')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page.locator('.err')).toBeVisible()
})

test('trabajador: marcar, mis marcas, justificar falta, bolsa; sin menus de gestion', async ({ page }) => {
  await login(page, 'trabajador@demo.gcb.pe')
  await abrir(page, 'Marcar asistencia', 'Registrar Asistencia')
  await abrir(page, 'Mis marcas', 'Mis marcas')
  await abrir(page, 'Justificar falta', 'Justificar una falta')
  await abrir(page, 'Mi bolsa de horas', 'Mi bolsa de horas')
  const nav = page.locator('nav')
  for (const m of ['Cierre de periodo', 'Bono 3 AM', 'Excepciones', 'Horarios']) {
    await expect(nav.getByRole('button', { name: m, exact: true })).toHaveCount(0)
  }
})

test('jefe: horarios, HE programadas, justificaciones, excepciones y reportes de su unidad', async ({ page }) => {
  await login(page, 'jefe@demo.gcb.pe')
  await abrir(page, 'Horarios', 'Asignación de horarios')
  await abrir(page, 'Horas extra programadas', 'Horas extra programadas')
  await abrir(page, 'Justificaciones', 'Justificación de faltas')
  await abrir(page, 'Excepciones', /Excepciones/)
  await abrir(page, 'Reportes', /Reportes/)
  await expect(page.locator('nav').getByRole('button', { name: 'Cierre de periodo', exact: true })).toHaveCount(0)
})

test('rrhh: cierre de periodo (solo ver checklist), bono 3 AM, trabajadores', async ({ page }) => {
  await login(page, 'rrhh@demo.gcb.pe')
  await abrir(page, 'Cierre de periodo', 'Cierre de periodo')
  await abrir(page, 'Bono 3 AM', 'Bono nocturno 3 AM')
  await abrir(page, 'Trabajadores', /Trabajadores/)
})

test('admin: reglas vigentes y salir', async ({ page }) => {
  await login(page, 'admin@demo.gcb.pe')
  await abrir(page, 'Reglas', 'Reglas vigentes (rule_set)')
  await page.getByRole('button', { name: 'Salir' }).click()
  await expect(page.getByPlaceholder('Correo')).toBeVisible()
})
