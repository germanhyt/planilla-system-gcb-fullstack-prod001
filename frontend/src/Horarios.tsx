import { useEffect, useState } from 'react'
import { api } from './api'

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const hoy = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const sumar = (d: string, n: number) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }
const lunes = (d: string) => { const x = new Date(d + 'T12:00:00'); return sumar(d, -((x.getDay() + 6) % 7)) }

/** Sprint 4: horario asignado por trabajador (patrón de 1..N semanas con vigencia) y calendario resuelto. */
export function Horarios({ rol }: { rol: string }) {
  const [trabs, setTrabs] = useState<any[]>([]); const [plantillas, setPlantillas] = useState<any[]>([])
  const [tid, setTid] = useState(''); const [asigs, setAsigs] = useState<any[]>([]); const [cal, setCal] = useState<any>(null)
  const [desde, setDesde] = useState(lunes(hoy())); const [hasta, setHasta] = useState('')
  const [patron, setPatron] = useState<(string)[][]>([Array(7).fill('')]); const [nota, setNota] = useState(''); const [msg, setMsg] = useState('')
  const gestor = rol !== 'trabajador'
  useEffect(() => {
    if (gestor) { api('/trabajadores').then(setTrabs).catch(() => {}); api('/turnos-plantilla').then(setPlantillas).catch(() => {}) }
  }, [])
  const t = trabs.find(x => String(x.id) === tid)
  const propias = plantillas.filter(p => t && p.unidad_id === t.unidad_id && p.activo)
  const cargar = () => {
    if (!tid) return
    api(`/asignaciones-horario?trabajador_id=${tid}`).then(setAsigs).catch(e => setMsg(e.message))
    api(`/asignaciones-horario/calendario?trabajador_id=${tid}&desde=${lunes(hoy())}&hasta=${sumar(lunes(hoy()), 27)}`).then(setCal).catch(() => setCal(null))
  }
  useEffect(() => { setMsg(''); cargar() }, [tid])
  const guardar = async () => {
    setMsg('')
    try {
      await api('/asignaciones-horario', { method: 'POST', body: { trabajador_id: Number(tid), vigente_desde: desde, vigente_hasta: hasta || null,
        patron: patron.map(s => s.map(v => v ? Number(v) : null)), nota: nota || null } })
      setMsg('Horario asignado.'); cargar()
    } catch (e: any) { setMsg(e.message) }
  }
  const eliminar = async (id: number) => {
    if (!confirm('¿Eliminar esta asignación?')) return
    try { await api(`/asignaciones-horario/${id}`, { method: 'DELETE' }); cargar() } catch (e: any) { setMsg(e.message) }
  }
  const nombre = (id: number | null) => id ? (plantillas.find(p => p.id === id)?.nombre ?? `#${id}`) : 'Descanso'
  if (!gestor) return <section><h2>Horarios</h2><p>Consulte su horario con su jefe.</p></section>
  return <section><h2>Asignación de horarios</h2>
    <label>Trabajador <select value={tid} onChange={e => setTid(e.target.value)}><option value="">—</option>
      {trabs.map(x => <option key={x.id} value={x.id}>{x.codigo} {x.nombres} {x.apellidos}</option>)}</select></label>
    {msg && <p>{msg}</p>}
    {t && <>
      <h3>Nueva asignación</h3>
      <p>El patrón rota cada semana desde la semana de inicio. Una programación semanal explícita tiene prioridad. Si el turno no define refrigerio se aplica el del tipo de contrato.</p>
      <label>Vigente desde <input type="date" value={desde} onChange={e => setDesde(e.target.value)} /></label>
      <label>Hasta (opcional) <input type="date" value={hasta} onChange={e => setHasta(e.target.value)} /></label>
      <table><thead><tr><th>Semana</th>{DIAS.map(d => <th key={d}>{d}</th>)}</tr></thead><tbody>
        {patron.map((s, i) => <tr key={i}><td>{i + 1}</td>{s.map((v, j) => <td key={j}>
          <select value={v} onChange={e => setPatron(patron.map((ss, ii) => ii !== i ? ss : ss.map((vv, jj) => jj === j ? e.target.value : vv)))}>
            <option value="">Descanso</option>{propias.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select></td>)}</tr>)}
      </tbody></table>
      <button onClick={() => setPatron([...patron, Array(7).fill('')])} disabled={patron.length >= 8}>+ semana</button>
      <button onClick={() => setPatron(patron.slice(0, -1))} disabled={patron.length <= 1}>− semana</button>
      <label>Nota <input value={nota} onChange={e => setNota(e.target.value)} /></label>
      <button onClick={guardar}>Asignar</button>
      <h3>Asignaciones</h3>
      <table><thead><tr><th>Desde</th><th>Hasta</th><th>Patrón</th><th>Nota</th><th></th></tr></thead><tbody>
        {asigs.map(a => <tr key={a.id}><td>{a.vigente_desde}</td><td>{a.vigente_hasta ?? 'abierta'}</td>
          <td>{a.patron.map((s: (number | null)[], i: number) => <div key={i}>S{i + 1}: {s.map(nombre).join(' · ')}</div>)}</td>
          <td>{a.nota}</td><td><button onClick={() => eliminar(a.id)}>Eliminar</button></td></tr>)}
      </tbody></table>
      {cal && <><h3>Próximas 4 semanas ({cal.contrato}, jornada {cal.jornada_diaria_min} min)</h3>
        <table><thead><tr><th>Día</th><th>Turno</th><th>Horario</th><th>Refrigerio</th><th>Horas</th><th>Origen</th></tr></thead><tbody>
          {cal.dias.map((d: any) => <tr key={d.dia}><td>{d.dia}</td><td>{d.plantilla ?? 'Descanso / sin horario'}</td>
            <td>{d.inicio ? `${d.inicio}–${d.fin}` : ''}</td><td>{d.refrigerio_min ?? ''}</td><td>{d.horas_programadas ?? ''}</td><td>{d.origen}</td></tr>)}
        </tbody></table></>}
    </>}
  </section>
}
