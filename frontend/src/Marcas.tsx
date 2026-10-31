/** Sprint 3: vistas de registros de marcas ("Mis marcas" para el trabajador, "Marcas" para jefe/RRHH). */
import { useEffect, useMemo, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, Clock, List, MapPin, QrCode, Search, SquarePen } from 'lucide-react'
import { api } from './api'
import { Button, Card, Field, PageHeader, Pantalla, Pill, Toolbar } from './ui'
import { Chips, DataTable, type ColumnDef } from './ui/DataTable'
import { conEmpresa, filtrarPorEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'

export interface MarcaVista {
  id: number; trabajador_id: number; trabajador_codigo: string; trabajador_nombre: string; unidad_id: number
  tipo: 'entrada' | 'salida'; ts_lima: string; fecha_lima: string; hora_lima: string
  origen: 'gps' | 'qr' | 'manual'; geocerca: 'dentro' | 'fuera' | 'sin_gps'; distancia_m: number | null
  dia_operativo: string; corte: string; razon_manual: string | null
}

const hoyLima = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const haceDias = (n: number) => new Date(Date.now() - n * 86400000).toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const ORIGEN = { gps: ['GPS', MapPin], qr: ['QR', QrCode], manual: ['Manual', SquarePen] } as const
type Geo = 'todas' | 'dentro' | 'fuera' | 'sin_gps'

function columnas(conTrabajador: boolean): ColumnDef<MarcaVista, any>[] {
  return [
    { accessorKey: 'dia_operativo', header: 'Día operativo', cell: c => <span title={`Corte ${c.row.original.corte}`}>{c.getValue()}</span> },
    ...(conTrabajador ? [{ id: 'trab', accessorFn: (m: MarcaVista) => `${m.trabajador_codigo} ${m.trabajador_nombre}`, header: 'Trabajador',
      cell: (c: any) => <span><b className="font-semibold">{c.row.original.trabajador_nombre}</b><span className="block text-xs text-muted">{c.row.original.trabajador_codigo}</span></span> }] : []),
    { accessorKey: 'tipo', header: 'Tipo', cell: c => c.getValue() === 'entrada'
      ? <Pill tono="accent"><ArrowUpRight size={12} />Entrada</Pill> : <Pill tono="neutral"><ArrowDownRight size={12} />Salida</Pill> },
    { accessorKey: 'fecha_lima', header: 'Fecha (Lima)' },
    { accessorKey: 'hora_lima', header: 'Hora servidor', cell: c => <span className="font-mono text-xs">{c.getValue()}</span> },
    { accessorKey: 'origen', header: 'Origen', cell: c => { const o = ORIGEN[c.getValue() as keyof typeof ORIGEN]; if (!o) return c.getValue()
      const I = o[1]; return <span className="inline-flex items-center gap-1.5 text-muted"><I size={14} aria-hidden />{o[0]}</span> } },
    { accessorKey: 'geocerca', header: 'Geocerca', cell: c => { const g = c.getValue()
      return g === 'dentro' ? <Pill tono="success">Dentro</Pill> : g === 'fuera' ? <Pill tono="danger">Fuera</Pill> : <Pill>Sin GPS</Pill> } },
    { accessorKey: 'distancia_m', header: 'Distancia', cell: c => c.getValue() != null ? `${Math.round(c.getValue())} m` : '—' },
  ]
}

function TablaMarcas({ marcas, conTrabajador, cargando, error, reintentar }: { marcas: MarcaVista[]; conTrabajador?: boolean; cargando: boolean; error: string; reintentar: () => void }) {
  const [geo, setGeo] = useState<Geo>('todas')
  const cols = useMemo(() => columnas(!!conTrabajador), [conTrabajador])
  const n = (g: Geo) => g === 'todas' ? marcas.length : marcas.filter(m => m.geocerca === g).length
  const datos = geo === 'todas' ? marcas : marcas.filter(m => m.geocerca === geo)
  return <DataTable data={datos} columns={cols} cargando={cargando} error={error} reintentar={reintentar} vacio="Sin marcas en el rango seleccionado." tam={15}
    buscar={conTrabajador ? 'Buscar trabajador, fecha…' : 'Buscar…'}
    chips={<Chips label="Geocerca" valor={geo} onChange={setGeo} chips={[{ valor: 'todas', label: 'Todas', n: n('todas') }, { valor: 'dentro', label: 'Dentro', n: n('dentro') },
      { valor: 'fuera', label: 'Fuera', n: n('fuera') }, { valor: 'sin_gps', label: 'Sin GPS', n: n('sin_gps') }]} />} />
}

function Rango({ desde, hasta, setDesde, setHasta }: { desde: string; hasta: string; setDesde: (v: string) => void; setHasta: (v: string) => void }) {
  return <>
    <Field label="Desde (día operativo)"><input type="date" className="ds-input" value={desde} onChange={e => setDesde(e.target.value)} /></Field>
    <Field label="Hasta"><input type="date" className="ds-input" value={hasta} onChange={e => setHasta(e.target.value)} /></Field>
  </>
}

function useCarga<T>(f: () => Promise<T>) {
  const [datos, setDatos] = useState<T | null>(null); const [err, setErr] = useState(''); const [cargando, setCargando] = useState(false)
  const run = () => { setErr(''); setCargando(true); f().then(setDatos).catch(e => setErr(e.message)).finally(() => setCargando(false)) }
  return { datos, err, cargando, run }
}

export function MisMarcas() {
  const [desde, setDesde] = useState(haceDias(6)); const [hasta, setHasta] = useState(hoyLima())
  const c = useCarga(() => api<MarcaVista[]>(`/marcas/mias?desde=${desde}&hasta=${hasta}`))
  useEffect(c.run, [])
  return <Pantalla>
    <PageHeader titulo="Mis marcas" icon={List} desc="Hora del servidor en America/Lima. Cavas: las marcas antes de las 06:00 cuentan para el día operativo anterior." />
    <Card><Toolbar><Rango {...{ desde, hasta, setDesde, setHasta }} /><Button variant="primary" icon={Search} onClick={c.run}>Buscar</Button></Toolbar></Card>
    <TablaMarcas marcas={c.datos ?? []} cargando={c.cargando || c.datos === null} error={c.err} reintentar={c.run} />
  </Pantalla>
}

export function MarcasEquipo({ rol }: { rol: string }) {
  const empresa = useEmpresaFiltro()
  const [desde, setDesde] = useState(haceDias(6)); const [hasta, setHasta] = useState(hoyLima())
  const [trabajadores, setTrabajadores] = useState<any[]>([]); const [unidades, setUnidades] = useState<any[]>([])
  const [trab, setTrab] = useState(''); const [unidad, setUnidad] = useState('')
  const c = useCarga(() => api<MarcaVista[]>(`/marcas/?${conEmpresa({ desde, hasta, trabajador_id: trab, unidad_id: unidad }, empresa)}`))
  useEffect(() => {
    api('/trabajadores').then(setTrabajadores).catch(() => {})
    if (rol !== 'jefe') api('/unidades').then(setUnidades).catch(() => {})
  }, [])
  useEffect(c.run, [empresa])
  const uds = filtrarPorEmpresa(unidades, empresa, u => u.empresa_id)
  const visibles = filtrarPorEmpresa(unidad ? trabajadores.filter(t => String(t.unidad_id) === unidad) : trabajadores, empresa, t => t.empresa_id)
  const m = c.datos ?? []
  return <Pantalla>
    <PageHeader titulo={`Marcas ${rol === 'jefe' ? 'de mi unidad' : ''}`.trim()} icon={Clock}
      desc={c.datos ? `${m.length} marcas · ${m.filter(x => x.geocerca === 'fuera').length} fuera de geocerca` : 'Registros de entrada y salida del equipo.'} />
    <Card><Toolbar><Rango {...{ desde, hasta, setDesde, setHasta }} />
      {rol !== 'jefe' && <Field label="Unidad"><select className="ds-input" value={unidad} onChange={e => { setUnidad(e.target.value); setTrab('') }}>
        <option value="">Todas</option>{uds.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></Field>}
      <Field label="Trabajador"><select className="ds-input" value={trab} onChange={e => setTrab(e.target.value)}>
        <option value="">Todos</option>{visibles.map(t => <option key={t.id} value={t.id}>{t.codigo} · {t.nombres} {t.apellidos}</option>)}</select></Field>
      <Button variant="primary" icon={Search} onClick={c.run}>Buscar</Button></Toolbar></Card>
    <TablaMarcas marcas={m} conTrabajador cargando={c.cargando || c.datos === null} error={c.err} reintentar={c.run} />
  </Pantalla>
}
