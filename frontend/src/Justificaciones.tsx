import { useEffect, useState } from 'react'
import { api } from './api'

const MOTIVOS: [string, string][] = [['permiso', 'Permiso'], ['licencia_medica', 'Licencia médica'], ['vacaciones', 'Vacaciones'], ['otro', 'Otro']]
const hoy = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })

/** Sprint 4: justificación de faltas. Trabajador solicita; jefe/RRHH aprueba o rechaza (o registra directo). */
export function Justificaciones({ rol }: { rol: string }) {
  const gestor = rol !== 'trabajador'
  const [lista, setLista] = useState<any[]>([]); const [trabs, setTrabs] = useState<any[]>([]); const [filtro, setFiltro] = useState(gestor ? 'pendiente' : '')
  const [f, setF] = useState({ trabajador_id: '', dia: hoy(), motivo: 'permiso', descripcion: '', adjunto_url: '' }); const [msg, setMsg] = useState('')
  const cargar = () => api(`/justificaciones${filtro ? `?estado=${filtro}` : ''}`).then(setLista).catch(e => setMsg(e.message))
  useEffect(() => { cargar() }, [filtro])
  useEffect(() => {
    if (gestor) api('/trabajadores').then(setTrabs).catch(() => {})
    else api('/me/trabajador').then((t: any) => t?.id && setF(x => ({ ...x, trabajador_id: String(t.id) }))).catch(() => {})
  }, [])
  const enviar = async () => {
    setMsg('')
    try {
      await api('/justificaciones', { method: 'POST', body: { ...f, trabajador_id: Number(f.trabajador_id), descripcion: f.descripcion || null, adjunto_url: f.adjunto_url || null } })
      setMsg(gestor ? 'Justificación registrada (aprobada).' : 'Solicitud enviada a su jefe.'); cargar()
    } catch (e: any) { setMsg(e.message) }
  }
  const decidir = async (id: number, aprobar: boolean) => {
    const comentario = aprobar ? '' : (prompt('Motivo del rechazo') ?? '')
    try { await api(`/justificaciones/${id}/decidir`, { method: 'POST', body: { aprobar, comentario: comentario || null } }); cargar() } catch (e: any) { setMsg(e.message) }
  }
  const retirar = async (id: number) => { try { await api(`/justificaciones/${id}`, { method: 'DELETE' }); cargar() } catch (e: any) { setMsg(e.message) } }
  return <section><h2>{gestor ? 'Justificación de faltas' : 'Justificar una falta'}</h2>
    <div className="form">
      {gestor && <label>Trabajador <select value={f.trabajador_id} onChange={e => setF({ ...f, trabajador_id: e.target.value })}><option value="">—</option>
        {trabs.map(t => <option key={t.id} value={t.id}>{t.codigo} {t.nombres} {t.apellidos}</option>)}</select></label>}
      <label>Día <input type="date" value={f.dia} onChange={e => setF({ ...f, dia: e.target.value })} /></label>
      <label>Motivo <select value={f.motivo} onChange={e => setF({ ...f, motivo: e.target.value })}>{MOTIVOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>Detalle <input value={f.descripcion} onChange={e => setF({ ...f, descripcion: e.target.value })} /></label>
      <label>Enlace a sustento (opcional) <input value={f.adjunto_url} onChange={e => setF({ ...f, adjunto_url: e.target.value })} /></label>
      <button disabled={!f.trabajador_id} onClick={enviar}>{gestor ? 'Registrar' : 'Enviar solicitud'}</button>
    </div>
    {msg && <p>{msg}</p>}
    <label>Estado <select value={filtro} onChange={e => setFiltro(e.target.value)}><option value="">Todos</option>
      <option value="pendiente">Pendientes</option><option value="aprobada">Aprobadas</option><option value="rechazada">Rechazadas</option></select></label>
    <table><thead><tr><th>Día</th><th>Trabajador</th><th>Motivo</th><th>Detalle</th><th>Estado</th><th></th></tr></thead><tbody>
      {lista.map(j => <tr key={j.id}><td>{j.dia}</td><td>{j.trabajador?.codigo} {j.trabajador?.nombres} {j.trabajador?.apellidos}</td>
        <td>{MOTIVOS.find(m => m[0] === j.motivo)?.[1] ?? j.motivo}</td><td>{j.descripcion}{j.adjunto_url && <> · <a href={j.adjunto_url} target="_blank" rel="noreferrer">sustento</a></>}</td>
        <td>{j.estado}{j.comentario_decision ? ` (${j.comentario_decision})` : ''}</td>
        <td>{j.estado === 'pendiente' && (gestor
          ? <><button onClick={() => decidir(j.id, true)}>Aprobar</button><button onClick={() => decidir(j.id, false)}>Rechazar</button></>
          : <button onClick={() => retirar(j.id)}>Retirar</button>)}</td></tr>)}
    </tbody></table>
  </section>
}
