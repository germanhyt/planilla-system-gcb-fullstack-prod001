import { describe, expect, it } from 'vitest'
import { numeroFila, paginas, pedirPagina, rango, urlPagina } from './DataTable'

describe('paginación numerada', () => {
  it('lista corta sin elipsis', () => expect(paginas(2, 5)).toEqual([1, 2, 3, 4, 5]))
  it('elipsis a ambos lados', () => expect(paginas(10, 20)).toEqual([1, '…', 9, 10, 11, '…', 20]))
  it('inicio y fin', () => { expect(paginas(1, 20)).toEqual([1, 2, '…', 20]); expect(paginas(20, 20)).toEqual([1, '…', 19, 20]) })
  it('texto Mostrando X a Y de Z', () => { expect(rango(2, 20, 45)).toBe('Mostrando 21 a 40 de 45'); expect(rango(3, 20, 45)).toBe('Mostrando 41 a 45 de 45'); expect(rango(1, 20, 0)).toBe('Sin resultados') })
})

describe('numeroFila', () => {
  it('continúa la numeración entre páginas', () => {
    expect(numeroFila(0, 10, 0)).toBe(1)
    expect(numeroFila(2, 20, 4)).toBe(45)
  })
})

describe('modo servidor: urlPagina + alRecibir (resumen/conteos)', () => {
  it('arma la URL omitiendo filtros vacíos', () => {
    expect(urlPagina('/x', { a: 1, b: '', c: null, d: 'z' }, 2, 20, '-dia', 'ana'))
      .toBe('/x?a=1&d=z&page=3&page_size=20&sort=-dia&q=ana')
    expect(urlPagina('/x?e=1', {}, 0, 10, '', '')).toBe('/x?e=1&page=1&page_size=10')
  })
  it('entrega la respuesta completa a alRecibir (claves extra incluidas)', async () => {
    const r = { items: [{ id: 1 }], total: 1, page: 1, page_size: 10, totales: { horas: 8 }, conteos: { pendiente: 3 } }
    const vistos: any[] = []
    const out = await pedirPagina(async () => r, '/x', () => true, x => vistos.push(x))
    expect(out).toBe(r)
    expect(vistos).toEqual([r])
    expect(vistos[0].totales.horas).toBe(8)
    expect(vistos[0].conteos.pendiente).toBe(3)
  })
  it('descarta respuestas obsoletas sin llamar a alRecibir', async () => {
    const vistos: any[] = []
    const out = await pedirPagina(async () => ({ items: [], total: 0, page: 1, page_size: 10 }), '/x', () => false, x => vistos.push(x))
    expect(out).toBeNull()
    expect(vistos).toEqual([])
  })
})
