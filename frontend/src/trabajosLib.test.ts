import { describe, expect, it, vi } from 'vitest'
import { esperarTrabajo, terminado, textoBadge, textoTrabajo, Trabajo } from './trabajosLib'

const t = (o: Partial<Trabajo>): Trabajo => ({ id: 1, tipo: 'recalcular', estado: 'en_proceso', progreso: 2, total: 4, porcentaje: 50, ...o })

describe('trabajosLib', () => {
  it('terminado solo en ok/error', () => {
    expect(terminado(t({}))).toBe(false); expect(terminado(t({ estado: 'ok' }))).toBe(true)
    expect(terminado(t({ estado: 'error' }))).toBe(true); expect(terminado(null)).toBe(false)
  })
  it('texto de progreso, cola y error', () => {
    expect(textoTrabajo(t({}))).toContain('2/4 (50%)')
    expect(textoTrabajo(t({ estado: 'pendiente', modo: 'rq', progreso: 0, porcentaje: 0 }))).toContain('worker')
    expect(textoTrabajo(t({ estado: 'error', error: 'boom' }))).toContain('boom')
    expect(textoTrabajo(t({ estado: 'ok', tipo: 'export_lote' }))).toBe('Exportacion por lote: completado (4/4)')
  })
  it('esperarTrabajo sondea hasta terminar', async () => {
    const seq = [t({ progreso: 1 }), t({ progreso: 3 }), t({ estado: 'ok', progreso: 4 })]
    const leer = vi.fn(async () => seq.shift()!); const av = vi.fn()
    const fin = await esperarTrabajo(1, leer, av, 0, 10, async () => {})
    expect(fin.estado).toBe('ok'); expect(av).toHaveBeenCalledTimes(3)
  })
  it('esperarTrabajo agota intentos', async () => {
    await expect(esperarTrabajo(1, async () => t({}), () => {}, 0, 2, async () => {})).rejects.toThrow('agotado')
  })
  it('badge', () => { expect(textoBadge(5)).toBe('5'); expect(textoBadge(150)).toBe('99+') })
})
