import { describe, expect, it } from 'vitest'
import { aplicar, CAMPOS_REGLA, convertir, diff, erroresGenerales, erroresPorCampo, leer, validarLocal } from './configLib'

const BASE = { tolerancia: { modo: 'umbral_perdona', minutos: 10 }, horas_extra: { destino_default: 'pago', pct_pago_mixto: 50 } }

describe('configLib', () => {
  it('aplicar no muta y fija rutas anidadas', () => {
    const r = aplicar(BASE, { 'tolerancia.minutos': 5, 'nocturno.mostrar_sobretasa_separada': true })
    expect(r.tolerancia).toEqual({ modo: 'umbral_perdona', minutos: 5 })
    expect(r.nocturno.mostrar_sobretasa_separada).toBe(true)
    expect(BASE.tolerancia.minutos).toBe(10)
  })
  it('diff lista solo cambios, con ruta', () => {
    expect(diff(BASE, aplicar(BASE, { 'horas_extra.pct_pago_mixto': 70 }))).toEqual([{ ruta: 'horas_extra.pct_pago_mixto', antes: 50, despues: 70 }])
    expect(diff(BASE, structuredClone(BASE))).toEqual([])
  })
  it('convertir respeta el tipo del campo', () => {
    const num = CAMPOS_REGLA.find(c => c.ruta === 'tolerancia.minutos')!
    const b = CAMPOS_REGLA.find(c => c.tipo === 'bool')!
    expect(convertir(num, '7')).toBe(7); expect(convertir(b, true)).toBe(true); expect(leer(BASE, 'tolerancia.modo')).toBe('umbral_perdona')
  })
  it('erroresPorCampo entiende el formato del backend y el de FastAPI', () => {
    expect(erroresPorCampo({ mensaje: 'x', errores: [{ campo: 'tolerancia.minutos', error: 'max 120' }] })).toEqual({ 'tolerancia.minutos': 'max 120' })
    expect(erroresPorCampo([{ loc: ['body', 'motivo'], msg: 'requerido' }])).toEqual({ motivo: 'requerido' })
    expect(erroresPorCampo('texto')).toEqual({})
  })
  it('tramos de HE: rutas con índice de arreglo sin mutar el original', () => {
    const b = { horas_extra: { sobretasas: [{ hasta_horas: 2, pct: 25 }, { hasta_horas: null, pct: 35 }] } }
    const r = aplicar(b, { 'horas_extra.sobretasas.0.pct': 30, 'horas_extra.sobretasas.0.hasta_horas': 1.5 })
    expect(r.horas_extra.sobretasas).toEqual([{ hasta_horas: 1.5, pct: 30 }, { hasta_horas: null, pct: 35 }])
    expect(b.horas_extra.sobretasas[0].pct).toBe(25)
    expect(leer(r, 'horas_extra.sobretasas.1.pct')).toBe(35)
  })
  it('erroresGenerales deja fuera los errores de campos del formulario', () => {
    expect(erroresGenerales({ 'nocturno.inicio': 'x', horas_extra: 'mínimo legal', motivo: 'm' })).toEqual(['horas_extra: mínimo legal'])
  })
  it('validarLocal exige vigencia futura y motivo', () => {
    expect(validarLocal('', '', '2026-10-30')).toHaveProperty('motivo')
    expect(validarLocal('2026-01-01', 'cambio', '2026-10-30').valid_from).toMatch(/retroactiva/)
    expect(validarLocal('2026-11-01', 'cambio', '2026-10-30')).toEqual({})
  })
})
