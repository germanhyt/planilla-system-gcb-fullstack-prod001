import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { descartar, encolar, listar, sincronizar, uuid } from './offlineQueue'

const base = (tipo: 'entrada' | 'salida', ts: string) => ({ id_idempotente: uuid(), tipo, lat: -12.1, lng: -77.0, ts_cliente: ts })

describe('cola offline de marcas', () => {
  beforeEach(async () => { for (const m of await listar()) await descartar(m.id_idempotente) })

  it('guarda en IndexedDB con uuid y ts del dispositivo, en orden', async () => {
    await encolar(base('salida', '2026-10-30T17:00:00-05:00'))
    await encolar(base('entrada', '2026-10-30T08:00:00-05:00'))
    const l = await listar()
    expect(l.map(m => m.tipo)).toEqual(['entrada', 'salida'])
    expect(l[0].id_idempotente).toMatch(/^[0-9a-f-]{36}$/)
    expect(l.every(m => m.estado === 'pendiente')).toBe(true)
  })

  it('envia con offline=true, borra las aceptadas y deja visibles las rechazadas (409)', async () => {
    const a = await encolar(base('entrada', '2026-10-30T08:00:00-05:00'))
    const b = await encolar(base('salida', '2026-10-30T17:00:00-05:00'))
    const enviados: any[] = []
    const r = await sincronizar(async body => {
      enviados.push(body)
      return body.id_idempotente === b.id_idempotente ? { status: 409, data: { detail: 'Periodo 2026-10 cerrado' } } : { status: 200, data: {} }
    })
    expect(r).toEqual({ enviadas: 1, rechazadas: 1, pendientes: 0 })
    expect(enviados.every(x => x.offline === true)).toBe(true)
    expect(enviados[0].id_idempotente).toBe(a.id_idempotente)
    const l = await listar()
    expect(l).toHaveLength(1)
    expect(l[0]).toMatchObject({ estado: 'rechazada', error: '409: Periodo 2026-10 cerrado' })
  })

  it('error de red: no pierde la marca y reintenta con el mismo id', async () => {
    const a = await encolar(base('entrada', '2026-10-30T08:00:00-05:00'))
    const r = await sincronizar(async () => { throw new TypeError('Failed to fetch') })
    expect(r.pendientes).toBe(1)
    const ids: string[] = []
    await sincronizar(async body => { ids.push(body.id_idempotente as string); return { status: 200, data: {} } })
    expect(ids).toEqual([a.id_idempotente])
    expect(await listar()).toHaveLength(0)
  })
})