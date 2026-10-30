/**
 * Cola offline de marcas (Sprint 3 / Inc 5). Si no hay red, la marca GPS/QR se guarda en IndexedDB con
 * ts del dispositivo, coordenadas y un UUID idempotente; se reenvia al volver la conexion. El backend
 * deduplica por id_idempotente, guarda ts_servidor de recepcion y la marca como 'diferida'.
 */
export type MarcaPendiente = {
  id_idempotente: string
  tipo: 'entrada' | 'salida'
  lat?: number
  lng?: number
  qr_code?: string
  ts_cliente: string
  estado: 'pendiente' | 'rechazada'
  error?: string
  intentos: number
}
export type Envio = (body: Record<string, unknown>) => Promise<{ status: number; data: any }>

const DB = 'planilla-offline', STORE = 'marcas', EVENTO = 'cola-offline-cambio'

export function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

function abrir(): Promise<IDBDatabase> {
  return new Promise((ok, mal) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id_idempotente' })
    req.onsuccess = () => ok(req.result)
    req.onerror = () => mal(req.error)
  })
}

async function tx<T>(modo: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await abrir()
  try {
    return await new Promise<T>((ok, mal) => {
      const req = fn(db.transaction(STORE, modo).objectStore(STORE))
      req.onsuccess = () => ok(req.result)
      req.onerror = () => mal(req.error)
    })
  } finally { db.close() }
}

const avisar = () => { if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENTO)) }

export async function encolar(m: Omit<MarcaPendiente, 'estado' | 'intentos'>): Promise<MarcaPendiente> {
  const item: MarcaPendiente = { ...m, estado: 'pendiente', intentos: 0 }
  await tx('readwrite', s => s.put(item))
  avisar()
  return item
}

export async function listar(): Promise<MarcaPendiente[]> {
  const items = await tx<MarcaPendiente[]>('readonly', s => s.getAll())
  return items.sort((a, b) => a.ts_cliente.localeCompare(b.ts_cliente))
}

export async function descartar(id: string): Promise<void> {
  await tx('readwrite', s => s.delete(id))
  avisar()
}

export type Resultado = { enviadas: number; rechazadas: number; pendientes: number; sesionExpirada: boolean }
let enCurso: Promise<Resultado> | null = null
export const EVENTO_SESION_EXPIRADA = 'sesion-expirada'

/** Envia en orden las pendientes. 2xx: se borra. 4xx (p.ej. 409 periodo cerrado): queda 'rechazada' visible.
 *  Error de red o 5xx: se detiene y reintenta luego. 401: se detiene, avisa 'sesion-expirada' y las marcas
 *  quedan pendientes; al volver a iniciar sesion se reintentan (ver reintentarTrasLogin). Llamadas concurrentes comparten la misma corrida. */
export function sincronizar(enviar: Envio) {
  if (enCurso) return enCurso
  enCurso = (async () => {
    let enviadas = 0, rechazadas = 0, sesionExpirada = false
    for (const m of await listar()) {
      if (m.estado !== 'pendiente') continue
      const { id_idempotente, tipo, lat, lng, qr_code, ts_cliente } = m
      let r: { status: number; data: any }
      try {
        r = await enviar({ id_idempotente, tipo, lat, lng, qr_code, ts_cliente, offline: true })
      } catch {
        await tx('readwrite', s => s.put({ ...m, intentos: m.intentos + 1 }))
        break
      }
      if (r.status === 401) {
        sesionExpirada = true
        if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENTO_SESION_EXPIRADA))
        break
      }
      if (r.status >= 200 && r.status < 300) {
        await tx('readwrite', s => s.delete(id_idempotente)); enviadas++
      } else if (r.status >= 400 && r.status < 500 && r.status !== 401 && r.status !== 408 && r.status !== 429) {
        const d = r.data?.detail
        await tx('readwrite', s => s.put({ ...m, estado: 'rechazada', intentos: m.intentos + 1,
          error: `${r.status}: ${typeof d === 'string' ? d : JSON.stringify(d ?? '')}` }))
        rechazadas++
      } else {
        await tx('readwrite', s => s.put({ ...m, intentos: m.intentos + 1 }))
        break
      }
    }
    const pendientes = (await listar()).filter(x => x.estado === 'pendiente').length
    avisar()
    return { enviadas, rechazadas, pendientes, sesionExpirada }
  })().finally(() => { enCurso = null })
  return enCurso
}

/** Reintento automatico: evento 'online', al volver a la pestana y cada 60 s. Devuelve la funcion de limpieza. */
export function autoSincronizar(enviar: Envio): () => void {
  const go = () => { if (navigator.onLine) sincronizar(enviar).catch(() => {}) }
  const vis = () => { if (document.visibilityState === 'visible') go() }
  window.addEventListener('online', go)
  document.addEventListener('visibilitychange', vis)
  const t = window.setInterval(go, 60000)
  go()
  return () => { window.removeEventListener('online', go); document.removeEventListener('visibilitychange', vis); clearInterval(t) }
}

/** Tras un login correcto: reenvia las marcas que quedaron pendientes (p. ej. por 401 con token vencido). */
export function reintentarTrasLogin(enviar: Envio = enviarApi) {
  return sincronizar(enviar).catch(() => null)
}

export function alCambiar(fn: () => void): () => void {
  window.addEventListener(EVENTO, fn)
  return () => window.removeEventListener(EVENTO, fn)
}

/** Envio real contra la API (no recarga en 401: la marca queda pendiente hasta volver a iniciar sesion). */
export const enviarApi: Envio = async body => {
  const token = localStorage.getItem('token')
  const r = await fetch('/api/marcas/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  })
  return { status: r.status, data: await r.json().catch(() => ({})) }
}