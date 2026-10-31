// Filtro global de empresa (top bar). Persistido en localStorage y difundido por evento a todas las pantallas.
import { useEffect, useState } from 'react'

export const KEY_EMPRESA = 'gcb-empresa-filtro'
export const EVENTO_EMPRESA = 'gcb-empresa-cambio'
type Store = { getItem(k: string): string | null; setItem(k: string, v: string): void }
const ls = (): Store | null => { try { return typeof localStorage === 'undefined' ? null : localStorage } catch { return null } }

export function leerEmpresa(s: Store | null = ls()): string {
  try { const v = s?.getItem(KEY_EMPRESA) ?? ''; return /^\d+$/.test(v) ? v : '' } catch { return '' }
}
export function guardarEmpresa(v: string, s: Store | null = ls(), w: { dispatchEvent(e: Event): boolean } | null = typeof window === 'undefined' ? null : window) {
  try { s?.setItem(KEY_EMPRESA, v) } catch { /* modo privado */ }
  w?.dispatchEvent(new CustomEvent(EVENTO_EMPRESA, { detail: v }))
}
/** Agrega empresa_id a un querystring si hay filtro activo. */
export function conEmpresa(params: Record<string, string | number | boolean | null | undefined>, empresa: string): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== '' && v !== null && v !== undefined) q.set(k, String(v))
  if (empresa) q.set('empresa_id', empresa)
  return q.toString()
}
/** Filtra filas en cliente para endpoints sin parámetro empresa_id (filas sin dato de empresa pasan). */
export function filtrarPorEmpresa<T>(filas: T[], empresa: string, get: (f: T) => unknown): T[] {
  if (!empresa) return filas
  return filas.filter(f => { const v = get(f); return v === undefined || v === null || String(v) === empresa })
}

export function useEmpresaFiltro(): string {
  const [v, setV] = useState(leerEmpresa)
  useEffect(() => {
    const f = () => setV(leerEmpresa()); window.addEventListener(EVENTO_EMPRESA, f); window.addEventListener('storage', f)
    return () => { window.removeEventListener(EVENTO_EMPRESA, f); window.removeEventListener('storage', f) }
  }, [])
  return v
}
