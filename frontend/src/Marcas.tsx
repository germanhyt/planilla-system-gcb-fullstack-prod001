/** Sprint 3: vistas de registros de marcas ("Mis marcas" para el trabajador, "Marcas" para jefe/RRHH). */
import { useEffect, useState } from 'react'
import { api } from './api'

export interface MarcaVista {
  id: number; trabajador_id: number; trabajador_codigo: string; trabajador_nombre: string; unidad_id: number
  tipo: 'entrada' | 'salida'; ts_lima: string; fecha_lima: string; hora_lima: string
  origen: 'gps' | 'qr' | 'manual'; geocerca: 'dentro' | 'fuera' | 'sin_gps'; distancia_m: number | null
  dia_operativo: string; corte: string; razon_manual: string | null
}

const hoyLima = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const haceDias = (n: number) => new Date(Date.now() - n * 86400000).toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const ORIGEN: Record<string, string> = { gps: '📍 GPS', qr: '📷 QR', manual: '✍️ Manual' }
const GEO: Record<string, string> = { dentro: '✅ Dentro', fuera: '⚠️ Fuera', sin_gps: '—' }

function Tabla({ marcas, conTrabajador }: { marcas: MarcaVista[]; conTrabajador?: boolean }) {
  if (!marcas.length) return <p>Sin marcas en el rango seleccionado.</p>
  return <table><thead><tr><th>Día operativo</th>{conTrabajador && <th>Trabajador</th>}<th>Tipo</th><th>Fecha (Lima)</th><th>Hora servidor (Lima)</th>
    <th>Origen</th><th>Geocerca</th><th>Distancia</th></tr></thead>
    <tbody>{marcas.map(m => <tr key={m.id}>
      <td title={`Corte ${m.corte}`}>{m.dia_operativo}</td>
      {conTrabajador && <td>{m.trabajador_codigo} · {m.trabajador_nombre}</td>}
      <td>{m.tipo === 'entrada' ? '⬆️ Entrada' : '⬇️ Salida'}</td><td>{m.fecha_lima}</td><td>{m.hora_lima}</td>
      <td>{ORIGEN[m.origen] ?? m.origen}</td><td>{GEO[m.geocerca] ?? m.geocerca}</td>
      <td>{m.distancia_m != null ? `${Math.round(m.distancia_m)} m` : '—'}</td></tr>)}</tbody></table>
}

function Rango({ desde, hasta, setDesde, setHasta }: { desde: string; hasta: string; setDesde: (v: string) => void; setHasta: (v: string) => void }) {
  return <>
    <label>Desde (día operativo) <input type="date" value={desde} onChange={e => setDesde(e.target.value)} /></label>
    <label>Hasta <input type="date" value={hasta} onChange={e => setHasta(e.target.value)} /></label>
  </>
}

export function MisMarcas() {
  const [desde, setDesde] = useState(haceDias(6)); const [hasta, setHasta] = useState(hoyLima())
  const [marcas, setMarcas] = useState<MarcaVista[] | null>(null); const [err, setErr] = useState('')
  const cargar = () => { setErr(''); api<MarcaVista[]>(`/marcas/mias?desde=${desde}&hasta=${hasta}`).then(setMarcas).catch(e => setErr(e.message)) }
  useEffect(cargar, [])
  return <section><h2>Mis marcas</h2>
    <div className="form"><Rango {...{ desde, hasta, setDesde, setHasta }} /><button onClick={cargar}>Buscar</button></div>
    {err && <p className="err">{err}</p>}
    {marcas && <Tabla marcas={marcas} />}
    <p style={{ fontSize: 12, color: '#666' }}>Hora del servidor en America/Lima. Cavas: las marcas antes de las 06:00 cuentan para el día operativo anterior.</p>
  </section>
}

export function MarcasEquipo({ rol }: { rol: string }) {
  const [desde, setDesde] = useState(haceDias(6)); const [hasta, setHasta] = useState(hoyLima())
  const [trabajadores, setTrabajadores] = useState<any[]>([]); const [unidades, setUnidades] = useState<any[]>([])
  const [trab, setTrab] = useState(''); const [unidad, setUnidad] = useState('')
  const [marcas, setMarcas] = useState<MarcaVista[] | null>(null); const [err, setErr] = useState('')
  const cargar = () => {
    setErr('')
    const q = new URLSearchParams({ desde, hasta }); if (trab) q.set('trabajador_id', trab); if (unidad) q.set('unidad_id', unidad)
    api<MarcaVista[]>(`/marcas/?${q}`).then(setMarcas).catch(e => setErr(e.message))
  }
  useEffect(() => {
    api('/trabajadores').then(setTrabajadores).catch(() => {})
    if (rol !== 'jefe') api('/unidades').then(setUnidades).catch(() => {})
    cargar()
  }, [])
  const visibles = unidad ? trabajadores.filter(t => String(t.unidad_id) === unidad) : trabajadores
  return <section><h2>Marcas {rol === 'jefe' ? 'de mi unidad' : ''}</h2>
    <div className="form"><Rango {...{ desde, hasta, setDesde, setHasta }} />
      {rol !== 'jefe' && <label>Unidad <select value={unidad} onChange={e => { setUnidad(e.target.value); setTrab('') }}>
        <option value="">Todas</option>{unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>}
      <label>Trabajador <select value={trab} onChange={e => setTrab(e.target.value)}>
        <option value="">Todos</option>{visibles.map(t => <option key={t.id} value={t.id}>{t.codigo} · {t.nombres} {t.apellidos}</option>)}</select></label>
      <button onClick={cargar}>Buscar</button></div>
    {err && <p className="err">{err}</p>}
    {marcas && <><p>{marcas.length} marcas · {marcas.filter(m => m.geocerca === 'fuera').length} fuera de geocerca</p><Tabla marcas={marcas} conTrabajador /></>}
  </section>
}
