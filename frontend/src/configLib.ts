// Lógica pura del módulo Configuración (testeable sin DOM).
export type Tipo = 'number' | 'bool' | 'time' | string[]
export interface CampoRegla { ruta: string; label: string; tipo: Tipo; ayuda?: string }
export interface Cambio { ruta: string; antes: unknown; despues: unknown }

export const CAMPOS_REGLA: CampoRegla[] = [
  { ruta: 'tolerancia.modo', label: 'Modo de tolerancia', tipo: ['umbral_perdona', 'umbral_descuenta_exceso', 'sin_tolerancia'] },
  { ruta: 'tolerancia.minutos', label: 'Tolerancia (min)', tipo: 'number' },
  { ruta: 'dia_operativo.tipo', label: 'Tipo de día', tipo: ['calendario', 'operativo'] },
  { ruta: 'dia_operativo.corte', label: 'Hora de corte del día', tipo: 'time', ayuda: 'Marcas antes de esta hora cuentan para el día anterior' },
  { ruta: 'horas_extra.destino_default', label: 'Destino HE por defecto', tipo: ['pago', 'compensacion', 'mixto'] },
  { ruta: 'horas_extra.pct_pago_mixto', label: '% a pago en mixto', tipo: 'number', ayuda: 'El resto va a la bolsa de horas' },
  { ruta: 'nocturno.mostrar_sobretasa_separada', label: 'Mostrar sobretasa nocturna separada', tipo: 'bool' },
  { ruta: 'part_time.alerta_promedio_diario_horas', label: 'Umbral PT (h promedio/día)', tipo: 'number' },
  { ruta: 'part_time.bloqueante', label: 'Alerta PT bloqueante', tipo: 'bool' },
  { ruta: 'marcacion_offline.umbral_diferida_min', label: 'Umbral marca diferida (min)', tipo: 'number' },
]

export function leer(obj: any, ruta: string): unknown {
  return ruta.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj)
}

/** Devuelve una copia de `base` con los valores del formulario aplicados (no muta). */
export function aplicar(base: Record<string, any>, valores: Record<string, unknown>): Record<string, any> {
  const out = structuredClone(base)
  for (const [ruta, v] of Object.entries(valores)) {
    const ks = ruta.split('.'); let o = out
    for (const k of ks.slice(0, -1)) o = (o[k] ??= {})
    o[ks[ks.length - 1]] = v
  }
  return out
}

/** Convierte el valor crudo de un input al tipo del campo. */
export function convertir(campo: CampoRegla, crudo: string | boolean): unknown {
  if (campo.tipo === 'bool') return Boolean(crudo)
  if (campo.tipo === 'number') return crudo === '' ? null : Number(crudo)
  return crudo
}

export function diff(a: any, b: any, ruta = ''): Cambio[] {
  const esObj = (x: unknown) => x !== null && typeof x === 'object' && !Array.isArray(x)
  if (esObj(a) && esObj(b)) {
    const ks = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()
    return ks.flatMap(k => diff(a[k], b[k], ruta ? `${ruta}.${k}` : k))
  }
  return JSON.stringify(a) === JSON.stringify(b) ? [] : [{ ruta, antes: a ?? null, despues: b ?? null }]
}

/** Mapea `detail` de un 422 (estructurado del backend o de FastAPI) a {campo: mensaje}. */
export function erroresPorCampo(detail: any): Record<string, string> {
  if (detail && Array.isArray(detail.errores)) return Object.fromEntries(detail.errores.map((e: any) => [e.campo, e.error]))
  if (Array.isArray(detail)) return Object.fromEntries(detail.map((e: any) => [(e.loc || []).filter((x: unknown) => x !== 'body').join('.'), e.msg]))
  return {}
}

export function validarLocal(valid_from: string, motivo: string, hoy: string): Record<string, string> {
  const e: Record<string, string> = {}
  if (!/^\d{4}-\d{2}-\d{2}$/.test(valid_from)) e.valid_from = 'Fecha de vigencia requerida'
  else if (valid_from < hoy) e.valid_from = 'La vigencia no puede ser retroactiva'
  if (motivo.trim().length < 3) e.motivo = 'Motivo requerido (mín. 3 caracteres)'
  return e
}
