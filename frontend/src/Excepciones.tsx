/** Sprint 3 / Incremento 2: bandeja de Excepciones (jefe su unidad, RRHH/admin todo) y Bolsa de horas. */
import { useEffect, useState } from 'react'
import { api } from './api'

const hoyLima = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const haceDias = (n: number) => new Date(Date.now() - n * 86400000).toLocaleDateString('en-CA', { timeZone: 'America/Lima' })

type Destino = 'pago' | 'compensacion' | 'mixto'
interface Item {
  clave: string; tipo: string; ref_id: number | null; trabajador: { id: number; codigo: string; nombre: string; unidad_id: number }
  empresa?: string; dia: string; detalle: string; horas?: number; estado: string; destino?: Destino | null
  destino_default?: Destino; observacion?: string | null; accionable: boolean; alerta_pt?: string | null
}
const TIPOS: Record<string, string> = { he_no_programada: 'HE no programada (no autorizada)', tardanza: 'Tardanza', fuera_geocerca: 'Marca fuera de geocerca', marca_diferida: 'Marca diferida (offline)', pt_alerta: 'Alerta part-time (PT85/PT102)' }
const DESTINOS: Record<Destino, string> = { pago: 'Pago (25% / 35%)', compensacion: 'Compensación (bolsa de horas)', mixto: 'Mixto' }
const ESTADO_COLOR: Record<string, string> = { pendiente: '#b26a00', aprobado: '#1b7f3b', rechazado: '#b00', informativo: '#555' }

function Decision({ it, onHecho }: { it: Item; onHecho: () => void }) {
  const [destino, setDestino] = useState<Destino>(it.destino_default ?? 'pago')
  const [horasPago, setHorasPago] = useState(String(((it.horas ?? 0) / 2).toFixed(2)))
  const [obs, setObs] = useState(''); const [err, setErr] = useState(''); const [enviando, setEnviando] = useState(false)
  const decidir = async (aprobar: boolean) => {
    if (!aprobar && !confirm('¿Rechazar el exceso? No se pagará ni irá a la bolsa de horas.')) return
    setEnviando(true); setErr('')
    try {
      const body: any = { aprobar, observacion: obs || undefined }
      if (aprobar) { body.destino = destino; if (destino === 'mixto') body.horas_pago = Number(horasPago) }
      await api(`/regularizaciones/${it.ref_id}/decidir`, { method: 'POST', body }); onHecho()
    } catch (e: any) { setErr(e.message) } finally { setEnviando(false) }
  }
  return <div className="decision">
    <select value={destino} onChange={e => setDestino(e.target.value as Destino)} title="Destino de las horas extra">
      {(Object.keys(DESTINOS) as Destino[]).map(d => <option key={d} value={d}>{DESTINOS[d]}{d === it.destino_default ? ' (por defecto)' : ''}</option>)}
    </select>
    {destino === 'mixto' && <label>Horas a pago <input type="number" step="0.25" min="0" max={it.horas} value={horasPago} onChange={e => setHorasPago(e.target.value)} style={{ width: 70 }} />
      <small>resto {Math.max(0, (it.horas ?? 0) - Number(horasPago)).toFixed(2)} h a bolsa</small></label>}
    <input placeholder="Observación (opcional)" value={obs} onChange={e => setObs(e.target.value)} />
    <button disabled={enviando} onClick={() => decidir(true)}>✔ Regularizar</button>
    <button disabled={enviando} onClick={() => decidir(false)}>✖ Rechazar</button>
    {err && <span className="err">{err}</span>}
  </div>
}

export function Excepciones({ rol }: { rol: string }) {
  const [desde, setDesde] = useState(haceDias(30)); const [hasta, setHasta] = useState(hoyLima())
  const [tipo, setTipo] = useState(''); const [estado, setEstado] = useState('pendiente'); const [unidad, setUnidad] = useState('')
  const [unidades, setUnidades] = useState<any[]>([]); const [items, setItems] = useState<Item[] | null>(null); const [err, setErr] = useState('')
  const cargar = () => {
    setErr('')
    const q = new URLSearchParams({ desde, hasta }); if (tipo) q.set('tipo', tipo); if (estado) q.set('estado', estado); if (unidad) q.set('unidad_id', unidad)
    api<Item[]>(`/excepciones/bandeja?${q}`).then(setItems).catch(e => setErr(e.message))
  }
  useEffect(() => { if (rol !== 'jefe') api('/unidades').then(setUnidades).catch(() => {}) }, [])
  useEffect(cargar, [tipo, estado, unidad])
  const pendientes = items?.filter(i => i.accionable).length ?? 0
  return <section><h2>Excepciones {rol === 'jefe' ? 'de mi unidad' : ''}</h2>
    <p style={{ fontSize: 13, color: '#555' }}>Las HE preautorizadas en el horario se pagan solas. El exceso no programado llega aquí como <b>no autorizado</b>; regularizarlo es opcional.
      Destino por defecto según empresa (CAVAS: pago · GCB SA: compensación). Las alertas PT85/PT102 (&gt;4 h/día de promedio semanal) son informativas y no bloquean.</p>
    <div className="form">
      <label>Desde <input type="date" value={desde} onChange={e => setDesde(e.target.value)} /></label>
      <label>Hasta <input type="date" value={hasta} onChange={e => setHasta(e.target.value)} /></label>
      <label>Tipo <select value={tipo} onChange={e => setTipo(e.target.value)}><option value="">Todos</option>
        {Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label>Estado <select value={estado} onChange={e => setEstado(e.target.value)}><option value="">Todos</option>
        {['pendiente', 'aprobado', 'rechazado', 'informativo'].map(s => <option key={s} value={s}>{s}</option>)}</select></label>
      {rol !== 'jefe' && <label>Unidad <select value={unidad} onChange={e => setUnidad(e.target.value)}><option value="">Todas</option>
        {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>}
      <button onClick={cargar}>Buscar</button></div>
    {err && <p className="err">{err}</p>}
    {items && <p>{items.length} excepciones · <b>{pendientes}</b> pendientes de decisión</p>}
    {items && !items.length && <p>Sin excepciones con esos filtros.</p>}
    {items && items.length > 0 && <table><thead><tr><th>Día</th><th>Trabajador</th><th>Tipo</th><th>Detalle</th><th>Estado</th><th>Acción</th></tr></thead>
      <tbody>{items.map(it => <tr key={it.clave}>
        <td>{it.dia}</td><td>{it.trabajador.codigo} · {it.trabajador.nombre}{it.empresa ? ` (${it.empresa})` : ''}</td>
        <td>{TIPOS[it.tipo] ?? it.tipo}</td>
        <td>{it.detalle}{it.alerta_pt && <div className="alerta">⚠ {it.alerta_pt} (no bloquea)</div>}{it.observacion && <div><small>Obs.: {it.observacion}</small></div>}</td>
        <td style={{ color: ESTADO_COLOR[it.estado] }}>{it.estado}{it.destino ? ` → ${DESTINOS[it.destino]}` : ''}</td>
        <td>{it.accionable ? <Decision it={it} onHecho={cargar} /> : '—'}</td></tr>)}</tbody></table>}
  </section>
}

interface Saldo { id: number; codigo: string; nombre: string; unidad_id: number; saldo_horas: number; movimientos: number; creditos_por_vencer_30d: number }

function Movimientos({ t }: { t: Saldo }) {
  const [movs, setMovs] = useState<any[] | null>(null); const [err, setErr] = useState('')
  useEffect(() => { setMovs(null); api(`/banco-horas/historial/${t.id}?limite=200`).then(r => setMovs(r.movimientos)).catch(e => setErr(e.message)) }, [t.id])
  return <div><h3>Movimientos · {t.codigo} {t.nombre} — saldo {t.saldo_horas.toFixed(2)} h</h3>
    {err && <p className="err">{err}</p>}
    {movs && !movs.length && <p>Sin movimientos.</p>}
    {movs && movs.length > 0 && <table><thead><tr><th>Fecha</th><th>Tipo</th><th>Horas</th><th>Saldo anterior</th><th>Saldo nuevo</th><th>Origen</th><th>Vence</th></tr></thead>
      <tbody>{movs.map(m => <tr key={m.id}><td>{m.fecha_movimiento}</td><td>{m.tipo === 'credito' ? '＋ Crédito' : '－ Débito'}</td>
        <td>{m.horas.toFixed(2)}</td><td>{m.saldo_anterior.toFixed(2)}</td><td><b>{m.saldo_nuevo.toFixed(2)}</b></td><td>{m.origen}</td><td>{m.fecha_expira ?? '—'}</td></tr>)}</tbody></table>}
  </div>
}

export function BolsaHoras({ rol }: { rol: string }) {
  const [saldos, setSaldos] = useState<Saldo[] | null>(null); const [sel, setSel] = useState<Saldo | null>(null)
  const [soloMov, setSoloMov] = useState(rol !== 'trabajador'); const [filtro, setFiltro] = useState(''); const [err, setErr] = useState('')
  useEffect(() => {
    api<Saldo[]>(`/banco-horas/saldos?solo_con_movimientos=${soloMov}`).then(s => { setSaldos(s); if (rol === 'trabajador' && s.length) setSel(s[0]) }).catch(e => setErr(e.message))
  }, [soloMov])
  if (rol === 'trabajador') return <section><h2>Mi bolsa de horas</h2>{err && <p className="err">{err}</p>}
    {saldos && !saldos.length && <p>No tienes una ficha de trabajador vinculada.</p>}
    {sel && <><p style={{ fontSize: 22 }}>Saldo disponible: <b>{sel.saldo_horas.toFixed(2)} h</b></p>
      {sel.creditos_por_vencer_30d > 0 && <p className="alerta">⚠ {sel.creditos_por_vencer_30d.toFixed(2)} h de crédito vencen en los próximos 30 días</p>}
      <Movimientos t={sel} /></>}</section>
  const vis = (saldos ?? []).filter(s => !filtro || `${s.codigo} ${s.nombre}`.toLowerCase().includes(filtro.toLowerCase()))
  return <section><h2>Bolsa de horas {rol === 'jefe' ? 'de mi unidad' : ''}</h2>
    <div className="form"><label>Buscar <input value={filtro} onChange={e => setFiltro(e.target.value)} placeholder="Código o nombre" /></label>
      <label style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}><input type="checkbox" checked={soloMov} onChange={e => setSoloMov(e.target.checked)} /> Sólo con movimientos</label></div>
    {err && <p className="err">{err}</p>}
    {saldos && <table><thead><tr><th>Código</th><th>Trabajador</th><th>Saldo (h)</th><th>Por vencer 30 d (h)</th><th>Movimientos</th><th></th></tr></thead>
      <tbody>{vis.map(s => <tr key={s.id} className={sel?.id === s.id ? 'sel' : ''}><td>{s.codigo}</td><td>{s.nombre}</td><td><b>{s.saldo_horas.toFixed(2)}</b></td>
        <td>{s.creditos_por_vencer_30d ? s.creditos_por_vencer_30d.toFixed(2) : '—'}</td><td>{s.movimientos}</td>
        <td><button onClick={() => setSel(s)}>Ver movimientos</button></td></tr>)}</tbody></table>}
    {sel && <Movimientos t={sel} />}
  </section>
}
