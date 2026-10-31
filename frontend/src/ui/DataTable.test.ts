import { describe, expect, it } from 'vitest'
import { numeroFila, paginas, rango } from './DataTable'

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
