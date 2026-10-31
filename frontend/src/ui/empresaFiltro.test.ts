import { describe, expect, it } from 'vitest'
import { conEmpresa, filtrarPorEmpresa, guardarEmpresa, KEY_EMPRESA, leerEmpresa } from './empresaFiltro'

const mem = () => { const m = new Map<string, string>(); return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), m } }

describe('filtro de empresa', () => {
  it('lee y guarda en gcb-empresa-filtro; valores no numéricos = todas', () => {
    const s = mem(); expect(leerEmpresa(s)).toBe('')
    const ev: Event[] = []; guardarEmpresa('7', s, { dispatchEvent: e => (ev.push(e), true) })
    expect(s.m.get(KEY_EMPRESA)).toBe('7'); expect(leerEmpresa(s)).toBe('7'); expect(ev).toHaveLength(1)
    s.setItem(KEY_EMPRESA, 'x;drop'); expect(leerEmpresa(s)).toBe('')
  })
  it('agrega empresa_id sólo si hay filtro y omite vacíos', () => {
    expect(conEmpresa({ periodo: '2026-08', estado: '' }, '')).toBe('periodo=2026-08')
    expect(conEmpresa({ periodo: '2026-08' }, '3')).toBe('periodo=2026-08&empresa_id=3')
  })
  it('filtra en cliente por empresa', () => {
    const f = [{ e: 1 }, { e: 2 }, { e: null }]
    expect(filtrarPorEmpresa(f, '', x => x.e)).toHaveLength(3)
    expect(filtrarPorEmpresa(f, '2', x => x.e)).toEqual([{ e: 2 }, { e: null }])
  })
})
