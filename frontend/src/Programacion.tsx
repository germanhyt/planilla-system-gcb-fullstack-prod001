import { useEffect, useState } from 'react'
import { api } from './api'

const hoy = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const sumarDias = (d: string, n: number) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }

/** Sprint 4: el jefe programa (preautoriza) horas extra por trabajador y día operativo.
 * Sólo lo programado se paga automáticamente; el exceso no programado llega a la bandeja como no autorizado. */
export function HEProgramadas({ rol }: { rol: string }) {
  const [desde, setDesde] = useState(hoy()); const [hasta, setHasta] = useState(sumarDias(hoy(), 13))
  const [trabs, setTrabs] = useState<any[]>([]); const [lista, setLista] = useState<any[]>([])
  const [f, setF] = useState({ trabajador_id: '', dia: hoy(), horas: '2', motivo: '' }); const [msg, setMsg] = useState('')
  const gestor = rol !== 'trabajador'
  const cargar = () => api(`/he-programadas?desde=${desde}&hasta=${hasta}`).then(setLista).catch(e => setMsg(e.message))
  useEffect(() => { cargar() }, [desde, hasta])
  useEffect(() => { if (gestor) api('/trabajadores').then(setTrabs).catch(() => {}) }, [])
  const guardar = async () => {
    setMsg('')
    try {
      await api('/he-programadas', { method: 'POST', body: { trabajador_id: Number(f.trabajador_id), dia: f.dia, horas: Number(f.horas), motivo: f.motivo || null } })
      setMsg('Horas extra programadas.'); cargar()
    } catch (e: any) { setMsg(e.message) }
  }
  const anular = async (id: number) => {
    if (!confirm('¿Anular esta programación?')) return
    try { await api(`/he-programadas/${id}`, { method: 'DELETE' }); cargar() } catch (e: any) { setMsg(e.message) }
  }
  return <section><h2>Horas extra programadas</h2>
    <p>Sólo las horas extra programadas aquí se pagan automáticamente (25 % las 2 primeras, 35 % el resto). El exceso no programado llega a la bandeja como <b>no autorizado</b>.</p>
    {gestor && <div className="form">
      <label>Trabajador <select value={f.trabajador_id} onChange={e => setF({ ...f, trabajador_id: e.target.value })}>
        <option value="">—</option>{trabs.map(t => <option key={t.id} value={t.id}>{t.codigo} {t.nombres} {t.apellidos}</option>)}</select></label>
      <label>Día operativo <input type="date" value={f.dia} onChange={e => setF({ ...f, dia: e.target.value })} /></label>
      <label>Horas <input type="number" step="0.25" min="0.25" max="12" value={f.horas} onChange={e => setF({ ...f, horas: e.target.value })} /></label>
      <label>Motivo <input value={f.motivo} onChange={e => setF({ ...f, motivo: e.target.value })} /></label>
      <button disabled={!f.trabajador_id} onClick={guardar}>Programar</button>
    </div>}
    <label>Desde <input type="date" value={desde} onChange={e => setDesde(e.target.value)} /></label>
    <label>Hasta <input type="date" value={hasta} onChange={e => setHasta(e.target.value)} /></label>
    {msg && <p>{msg}</p>}
    <table><thead><tr><th>Día</th><th>Trabajador</th><th>Horas</th><th>Motivo</th>{gestor && <th></th>}</tr></thead>
      <tbody>{lista.map(h => <tr key={h.id}><td>{h.dia}</td><td>{h.trabajador?.codigo} {h.trabajador?.nombres} {h.trabajador?.apellidos}</td>
        <td>{h.horas}</td><td>{h.motivo}</td>{gestor && <td><button onClick={() => anular(h.id)}>Anular</button></td>}</tr>)}</tbody></table>
  </section>
}
