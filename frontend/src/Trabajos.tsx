/** Sprint 7: notificaciones RRHH, progreso de trabajos y versiones de export Planilla Core. */
import { useEffect, useState } from 'react'
import { api, getToken } from './api'
import { esperarTrabajo, ETIQUETA_ALERTA, textoTrabajo, Trabajo } from './trabajosLib'

export function ProgresoTrabajo({ t }: { t: Trabajo | null }) {
  if (!t) return null
  return <div data-testid="progreso-trabajo" style={{ margin: '6px 0' }}>
    <progress max={100} value={t.porcentaje} style={{ width: 240 }} /> <span>{textoTrabajo(t)}</span></div>
}

/** Lanza un POST que puede devolver un trabajo y sigue su progreso. */
export function useTrabajo() {
  const [t, setT] = useState<Trabajo | null>(null)
  const seguir = (tr: Trabajo) => { setT(tr); return esperarTrabajo(tr.id, id => api<Trabajo>(`/trabajos/${id}`), x => setT({ ...x, modo: tr.modo })) }
  return { trabajo: t, seguir, limpiar: () => setT(null) }
}

export function useConteoNotificaciones(activo: boolean, refrescar = 0) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!activo) return
    const leer = () => api<{ no_leidas: number }>('/notificaciones/conteo').then(r => setN(r.no_leidas)).catch(() => {})
    leer(); const h = setInterval(leer, 60000); return () => clearInterval(h)
  }, [activo, refrescar])
  return n
}

const mesActual = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' }).slice(0, 7)

export function Notificaciones({ onCambio }: { onCambio?: () => void }) {
  const [lista, setLista] = useState<any[]>([]); const [periodo, setPeriodo] = useState(mesActual()); const [msg, setMsg] = useState('')
  const [soloNoLeidas, setSoloNoLeidas] = useState(false)
  const cargar = () => api<any[]>(`/notificaciones?solo_no_leidas=${soloNoLeidas}`).then(setLista).catch(e => setMsg(e.message))
  useEffect(() => { cargar() }, [soloNoLeidas])
  const generar = async () => {
    setMsg('')
    try { await api(`/notificaciones/generar?periodo=${periodo}`, { method: 'POST' }); setMsg(`Alertas de ${periodo} evaluadas.`); cargar(); onCambio?.() }
    catch (e: any) { setMsg(e.message) }
  }
  const leer = async (n: any) => { await api(`/notificaciones/${n.id}/leida`, { method: 'POST' }).catch(() => {}); cargar(); onCambio?.() }
  return <section><h2>Notificaciones RRHH</h2>
    <p style={{ fontSize: 13, color: '#555' }}>Alertas internas: asistencia decidida que perdio sus marcas, pendientes cerca del cierre, riesgo part time y bonos sin aprobar. Se resuelven solas al corregirse la causa.</p>
    <div className="form">
      <label>Periodo <input type="month" value={periodo} onChange={e => setPeriodo(e.target.value)} /></label>
      <button onClick={generar}>Evaluar alertas</button>
      <label><span><input type="checkbox" checked={soloNoLeidas} onChange={e => setSoloNoLeidas(e.target.checked)} /> Solo no leidas</span></label>
    </div>
    {msg && <p>{msg}</p>}
    {lista.length === 0 ? <p>Sin alertas activas.</p> :
      <table><thead><tr><th>Tipo</th><th>Periodo</th><th>Mensaje</th><th>Creada</th><th></th></tr></thead>
        <tbody>{lista.map(n => <tr key={n.id} style={{ fontWeight: n.leida ? 'normal' : 'bold' }}><td>{ETIQUETA_ALERTA[n.tipo] || n.tipo}</td><td>{n.periodo}</td><td>{n.mensaje}</td>
          <td>{n.creada_en ? new Date(n.creada_en).toLocaleString('es-PE', { timeZone: 'America/Lima' }) : ''}</td>
          <td>{!n.leida && <button onClick={() => leer(n)}>Marcar leida</button>}</td></tr>)}</tbody></table>}
  </section>
}

export async function descargarVersion(id: number) {
  const r = await fetch(`/api/reportes/export-planilla-core/versiones/${id}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!r.ok) throw new Error(String(r.status))
  const nombre = /filename=([^;]+)/.exec(r.headers.get('content-disposition') || '')?.[1] || 'export'
  const url = URL.createObjectURL(await r.blob()); const a = document.createElement('a'); a.href = url; a.download = nombre; a.click(); URL.revokeObjectURL(url)
}

export function VersionesExport({ empresa, periodo, recarga }: { empresa: string; periodo: string; recarga: number }) {
  const [vs, setVs] = useState<any[]>([])
  useEffect(() => {
    if (!empresa) { setVs([]); return }
    api<any[]>(`/reportes/export-planilla-core/versiones?empresa_id=${empresa}&periodo=${periodo}`).then(setVs).catch(() => setVs([]))
  }, [empresa, periodo, recarga])
  if (!empresa) return null
  return <div data-testid="versiones-export"><h3>Versiones exportadas {periodo}</h3>
    {vs.length === 0 ? <p>Sin exportaciones registradas.</p> :
      <table><thead><tr><th>Version</th><th>Formato</th><th>Estado</th><th>Layout</th><th>Trabajadores</th><th>Lineas</th><th>Checksum</th><th>Generado</th><th></th></tr></thead>
        <tbody>{vs.map(v => <tr key={v.id}><td>v{v.version}</td><td>{v.formato}</td><td>{v.estado}</td><td>{v.layout_version}</td><td>{v.trabajadores}</td><td>{v.lineas}</td>
          <td title={v.checksum}><code>{String(v.checksum).slice(0, 12)}</code></td>
          <td>{v.generado_en ? new Date(v.generado_en).toLocaleString('es-PE', { timeZone: 'America/Lima' }) : ''}</td>
          <td><button onClick={() => descargarVersion(v.id)}>Descargar</button></td></tr>)}</tbody></table>}
  </div>
}
