import { expect, test, APIRequestContext } from '@playwright/test'
import { abrir, login, PASSWORD } from './helpers'

// Sprint 6: flujo GCB SA (GRUPO CORDILLERA BLANCA S.A.) con alcance multiempresa.
async function token(request: APIRequestContext, email: string) {
  const r = await request.post('/api/auth/login', { data: { email, password: PASSWORD } })
  expect(r.ok()).toBeTruthy()
  return { Authorization: `Bearer ${(await r.json()).access_token}` }
}

test('rrhh GCB: UI de trabajadores y API solo con datos de su empresa', async ({ page, request }) => {
  await login(page, 'rrhh.gcb@demo.gcb.pe')
  await abrir(page, 'Trabajadores', /Trabajadores/)
  await expect(page.getByText('REF-001').first()).toBeVisible()

  const h = await token(request, 'rrhh.gcb@demo.gcb.pe')
  const emp = await (await request.get('/api/empresas', { headers: h })).json()
  expect(emp.map((e: { razon_social: string }) => e.razon_social)).toEqual(['GRUPO CORDILLERA BLANCA S.A.'])
  const ts = await (await request.get('/api/trabajadores', { headers: h })).json()
  for (const t of ts) expect(t.empresa_id).toBe(emp[0].id)
  const otra = await request.get('/api/reportes/consolidado-mensual?empresa_id=999999', { headers: h })
  expect([403, 404, 422]).toContain(otra.status())
})

test('jefe Refugio: abre reportes y la API solo le devuelve trabajadores REF', async ({ page, request }) => {
  await login(page, 'jefe.refugio@demo.gcb.pe')
  await abrir(page, 'Reportes', /Reportes/)
  const h = await token(request, 'jefe.refugio@demo.gcb.pe')
  const ts = await (await request.get('/api/trabajadores', { headers: h })).json()
  expect(ts.length).toBeGreaterThan(0)
  for (const t of ts) expect(t.codigo).toMatch(/^REF-/)
})
