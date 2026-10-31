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

test('rrhh: configuracion en solo lectura', async ({ page }) => {
  await login(page, 'rrhh@demo.gcb.pe')
  await abrir(page, 'Configuración', 'Configuración')
  await expect(page.getByText('Solo lectura')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Valores vigentes' })).toBeVisible()
  await expect(page.getByLabel('Tolerancia (min)')).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Previsualizar cambios' })).toHaveCount(0)
})

test('jefe: reglas vigentes (solo consulta)', async ({ page }) => {
  await login(page, 'jefe@demo.gcb.pe')
  await abrir(page, 'Reglas', 'Reglas vigentes (rule_set)')
  await expect(page.locator('nav').getByRole('button', { name: 'Configuración' })).toHaveCount(0)
})

// Configuración: SOLO previsualiza y valida; nunca publica versiones (seguro contra dev).
test('admin: configuracion - historial, validaciones y preview del diff, y salir', async ({ page }) => {
  await login(page, 'admin@demo.gcb.pe')
  await abrir(page, 'Configuración', 'Configuración')
  await expect(page.getByRole('heading', { name: 'Historial de versiones' })).toBeVisible()
  await expect(page.getByText('(vigente)')).toBeVisible()
  await page.getByRole('button', { name: 'Previsualizar cambios' }).click()
  await expect(page.locator('[data-campo="motivo"]')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Publicar versión' })).toBeDisabled()
  await page.getByLabel('Vigente desde').fill('2099-01-01')
  await page.getByLabel('Motivo').fill('prueba e2e (no se publica)')
  const tol = page.getByLabel('Tolerancia (min)')
  await tol.fill('500')
  await page.getByRole('button', { name: 'Previsualizar cambios' }).click()
  await expect(page.locator('[data-campo="tolerancia.minutos"]')).toBeVisible()
  await tol.fill('3')
  await page.getByRole('button', { name: 'Previsualizar cambios' }).click()
  await expect(page.getByRole('cell', { name: 'tolerancia.minutos' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Publicar versión' })).toBeEnabled()
  // Tramos de HE y ventana nocturna: validación (mínimo legal) y diff, sin publicar
  const p1 = page.getByLabel('% HE 1.er tramo')
  await p1.fill('20')
  await page.getByRole('button', { name: 'Previsualizar cambios' }).click()
  await expect(page.getByRole('alert')).toContainText('mínimo legal')
  await p1.fill('30')
  await page.getByLabel('Nocturno: inicio').fill('21:00')
  await page.getByRole('button', { name: 'Previsualizar cambios' }).click()
  await expect(page.getByRole('cell', { name: 'horas_extra.sobretasas' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'nocturno.inicio' })).toBeVisible()
  await page.locator('section nav').getByRole('button', { name: 'Tipos de contrato' }).click()
  await expect(page.getByRole('heading', { name: 'Tipos de contrato' })).toBeVisible()
  await page.getByRole('button', { name: 'Menú de usuario' }).click()
  await page.getByRole('menuitem', { name: 'Salir' }).click()
  await expect(page.getByPlaceholder('Correo')).toBeVisible()
})
