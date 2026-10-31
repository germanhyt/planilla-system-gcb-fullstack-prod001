/** Sprint 7: utilidades puras para trabajos en segundo plano (RQ) y notificaciones. */
export interface Trabajo {
  id: number; tipo: string; estado: string; progreso: number; total: number; porcentaje: number
  resultado?: any; error?: string | null; modo?: string
}
export const FINALES = ['ok', 'error']
export const terminado = (t: Trabajo | null | undefined) => !!t && FINALES.includes(t.estado)
export function textoTrabajo(t: Trabajo): string {
  const nombre = t.tipo === 'export_lote' ? 'Exportacion por lote' : t.tipo === 'recalcular' ? 'Recalculo' : t.tipo
  if (t.estado === 'ok') return `${nombre}: completado (${t.total}/${t.total})`
  if (t.estado === 'error') return `${nombre}: error - ${t.error || 'desconocido'}`
  const cola = t.modo === 'rq' && t.estado === 'pendiente' ? ' (en cola; requiere worker activo)' : ''
  return `${nombre}: ${t.estado} ${t.progreso}/${t.total} (${t.porcentaje}%)${cola}`
}
/** Consulta el trabajo hasta que termine; llama onAvance en cada lectura. */
export async function esperarTrabajo(id: number, leer: (id: number) => Promise<Trabajo>, onAvance: (t: Trabajo) => void,
  intervaloMs = 1000, maxIntentos = 600, dormir = (ms: number) => new Promise(r => setTimeout(r, ms))): Promise<Trabajo> {
  for (let i = 0; i < maxIntentos; i++) {
    const t = await leer(id); onAvance(t)
    if (terminado(t)) return t
    await dormir(intervaloMs)
  }
  throw new Error('Tiempo de espera agotado para el trabajo ' + id)
}
export const ETIQUETA_ALERTA: Record<string, string> = {
  asistencia_sin_marcas: 'Asistencia decidida sin marcas', pendientes_cierre: 'Pendientes cerca del cierre',
  pt_riesgo: 'Riesgo part time', bonos_sin_aprobar: 'Bonos sin aprobar',
}
export const textoBadge = (n: number) => (n > 99 ? '99+' : String(n))
