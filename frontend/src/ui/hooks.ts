import { useCallback, useState } from 'react'

/** Carga asíncrona con estados (datos/null mientras no hay, error y cargando). */
export function useCarga<T>(f: () => Promise<T>, deps: unknown[] = []) {
  const [datos, setDatos] = useState<T | null>(null); const [err, setErr] = useState(''); const [cargando, setCargando] = useState(false)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(() => { setErr(''); setCargando(true); return f().then(d => { setDatos(d); return d }).catch(e => { setErr(e.message); return null }).finally(() => setCargando(false)) }, deps)
  return { datos, setDatos, err, cargando: cargando || (datos === null && !err), run }
}
export const hoyLima = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
export const mesLima = () => hoyLima().slice(0, 7)
export const fechaHora = (v?: string | null) => v ? new Date(v).toLocaleString('es-PE', { timeZone: 'America/Lima' }) : ''
export const nombreTrab = (t: any) => t ? `${t.codigo ?? ''} ${t.nombres ?? ''} ${t.apellidos ?? ''}`.trim() : ''
