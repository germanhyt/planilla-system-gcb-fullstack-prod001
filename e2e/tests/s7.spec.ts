import { expect, test, APIRequestContext } from '@playwright/test'
import { abrir, login, PASSWORD } from './helpers'

// Sprint 7: integracion Planilla Core (export versionado), trabajos en segundo plano y notificaciones RRHH.
const PER = '2026-08'
async function token(request: APIRequestContext, email: string) {
  const r = await request.post('/api/auth/login', { data: { email, password: PASSWORD } })
  expect(r.ok()).toBeTruthy()
  return { Authorization: `Bearer ${(await r.json()).access_token}` }
}

test('export PC-ASIS-1.1: contrato, checksum y re-export idempotente', async ({ request }) => {
  const h = await token(request, 'rrhh.gcb@demo.gcb.pe')
  const contrato = await (await request.get('/api/reportes/export-planilla-core/contrato', { headers: h })).json()
  expect(JSON.stringify(contrato)).toContain('PC-ASIS-1.1')
  const emp = (await (await request.get('/api/empresas', { headers: h })).json())[0]
  const url = `/api/reportes/export-planilla-core?empresa_id=${emp.id}&periodo=${PER}&formato=json`
  const a = await request.post(url, { headers: h }); expect(a.ok()).toBeTruthy()
  const b = await request.post(url, { headers: h }); expect(b.ok()).toBeTruthy()
  expect(b.headers()['x-export-checksum']).toBe(a.headers()['x-export-checksum'])
  expect(b.headers()['x-export-reutilizada']).toBe('1')
  expect(b.headers()['x-export-version']).toBe(a.headers()['x-export-version'])
  const vs = await (await request.get(`/api/reportes/export-planilla-core/versiones?empresa_id=${emp.id}&periodo=${PER}`, { headers: h })).json()
  expect(vs.length).toBeGreaterThan(0)
  expect(vs[0].layout_version).toBe('PC-ASIS-1.1')
})

test('export por lote como trabajo con progreso hasta terminar', async ({ request }) => {
  const h = await token(request, 'rrhh.gcb@demo.gcb.pe')
  const t = await (await request.post(`/api/reportes/export-planilla-core/lote?periodo=${PER}&formato=csv`, { headers: h })).json()
  expect(t.tipo).toBe('export_lote')
  let fin = t
  for (let i = 0; i < 30 && !['ok', 'error'].includes(fin.estado); i++) {
    await new Promise(r => setTimeout(r, 1000))
    fin = await (await request.get(`/api/trabajos/${t.id}`, { headers: h })).json()
  }
  expect(fin.estado).toBe('ok'); expect(fin.porcentaje).toBe(100)
})

test('UI: historial de versiones en Reportes y vista de notificaciones', async ({ page }) => {
  await login(page, 'rrhh.gcb@demo.gcb.pe')
  await abrir(page, 'Reportes', /Reportes/)
  await page.locator('input[type=month]').fill(PER)
  await expect(page.getByTestId('versiones-export')).toBeVisible()
  await expect(page.getByTestId('versiones-export').getByText('PC-ASIS-1.1').first()).toBeVisible()
  await page.locator('nav').getByRole('button', { name: /^Notificaciones/ }).click()
  await expect(page.getByRole('heading', { name: 'Notificaciones RRHH' })).toBeVisible()
  await page.locator('input[type=month]').fill(PER)
  await page.getByRole('button', { name: 'Evaluar alertas' }).click()
  await expect(page.getByText(`Alertas de ${PER} evaluadas.`)).toBeVisible()
})

test('jefe no accede a notificaciones ni trabajos', async ({ request }) => {
  const h = await token(request, 'jefe.refugio@demo.gcb.pe')
  expect((await request.get('/api/notificaciones', { headers: h })).status()).toBe(403)
  expect((await request.get('/api/trabajos', { headers: h })).status()).toBe(403)
})
