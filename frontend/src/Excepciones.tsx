/** Sprint 3 / Incremento 2: bandeja de Excepciones (jefe su unidad, RRHH/admin todo) y Bolsa de horas. */
import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Check, Clock3, Hourglass, Inbox, PiggyBank, Search, TrendingDown, TrendingUp, X } from 'lucide-react'
import { api } from './api'
import { Aviso, Button, Card, Field, KpiCard, PageHeader, Pantalla, Pill, PillEstado, Toolbar, cn } from './ui'
import { Chips, DataTable, type ColumnDef } from './ui/DataTable'
import { confirmar, fallo, ok } from './ui/feedback'
import { conEmpresa, filtrarPorEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { hoyLima, useCarga } from './ui/hooks'

const haceDias = (n: number) => new Date(Date.now() - n * 86400000).toLocaleDateString('en-CA', { timeZone: 'America/Lima' })

type Destino = 'pago' | 'compensacion' | 'mixto'
export interface Item {
  clave: string; tipo: string; ref_id: number | null; trabajador: { id: number; codigo: string; nombre: string; unidad_id: number }
  empresa?: string; dia: string; detalle: string; horas?: number; estado: string; destino?: Destino | null
  destino_default?: Destino; observacion?: string | null; accionable: boolean; alerta_pt?: string | null
}
export const TIPOS: Record<string, string> = { he_no_programada: 'HE no programada (no autorizada)', tardanza: 'Tardanza', fuera_geocerca: 'Marca fuera de geocerca', marca_diferida: 'Marca diferida (offline)', pt_alerta: 'Alerta part-time (PT85/PT102)' }
const DESTINOS: Record<Destino, string> = { pago: 'Pago (25% / 35%)', compensacion: 'Compensación (bolsa de horas)', mixto: 'Mixto' }
type Estado = '' | 'pendiente' | 'aprobado' | 'rechazado' | 'informativo'

function Decision({ it, onHecho }: { it: Item; onHecho: () => void }) {
  const [destino, setDestino] = useState<Destino>(it.destino_default ?? 'pago')
  const [horasPago, setHorasPago] = useState(String(((it.horas ?? 0) / 2).toFixed(2)))
  const [obs, setObs] = useState(''); const [enviando, setEnviando] = useState(false)
  const decidir = async (aprobar: boolean) => {
    if (!aprobar && !await confirmar({ titulo: '¿Rechazar el exceso?', mensaje: 'No se pagará ni irá a la bolsa de horas.', peligro: true, ok: 'Rechazar' })) return
    setEnviando(true)
    try {
      const body: any = { aprobar, observacion: obs || undefined }
      if (aprobar) { body.destino = destino; if (destino === 'mixto') body.horas_pago = Number(horasPago) }
      await api(`/regularizaciones/${it.ref_id}/decidir`, { method: 'POST', body }); ok(aprobar ? `Regularizado: ${DESTINOS[destino]}.` : 'Exceso rechazado.'); onHecho()
    } catch (e) { fallo(e) } finally { setEnviando(false) }
  }
  return <div className="flex min-w-[260px] flex-wrap items-center gap-1.5">
    <select className="ds-input h-8 !py-0 text-xs" value={destino} onChange={e => setDestino(e.target.value as Destino)} title="Destino de las horas extra" aria-label="Destino de las horas extra">
      {(Object.keys(DESTINOS) as Destino[]).map(d => <option key={d} value={d}>{DESTINOS[d]}{d === it.destino_default ? ' (por defecto)' : ''}</option>)}
    </select>
    {destino === 'mixto' && <label className="flex items-center gap-1 text-xs text-muted">Horas a pago <input type="number" step="0.25" min="0" max={it.horas} value={horasPago} onChange={e => setHorasPago(e.target.value)} className="ds-input h-8 w-16 !py-0" />
      <small>resto {Math.max(0, (it.horas ?? 0) - Number(horasPago)).toFixed(2)} h a bolsa</small></label>}
    <input className="ds-input h-8 w-40 !py-0 text-xs" placeholder="Observación (opcional)" aria-label="Observación" value={obs} onChange={e => setObs(e.target.value)} />
    <Button size="sm" variant="primary" icon={Check} disabled={enviando} onClick={() => decidir(true)}>Regularizar</Button>
    <Button size="sm" variant="danger" icon={X} disabled={enviando} onClick={() => decidir(false)}>Rechazar</Button>
  </div>
}

export function Excepciones({ rol }: { rol: string }) {
  const empresa = useEmpresaFiltro()
  const [desde, setDesde] = useState(haceDias(30)); const [hasta, setHasta] = useState(hoyLima())
  const [tipo, setTipo] = useState(''); const [estado, setEstado] = useState<Estado>('pendiente'); const [unidad, setUnidad] = useState('')
  const [unidades, setUnidades] = useState<any[]>([])
  // S8 paso 7: paginada en la BD; los KPI vienen en `resumen` (mismos filtros, no sólo la página)
  const [rango, setRango] = useState({ desde, hasta }); const [recarga, setRecarga] = useState(0)
  const [resumen, setResumen] = useState<{ total: number; pendientes: number; fuera_geocerca: number } | null>(null)
  const run = () => { setRango({ desde, hasta }); setRecarga(n => n + 1) }
  useEffect(() => { if (rol !== 'jefe') api('/unidades').then(setUnidades).catch(() => {}) }, [])
  const params = { ...rango, tipo, estado, unidad_id: unidad, empresa_id: empresa }
  const cols = useMemo<ColumnDef<Item, any>[]>(() => [
    { accessorKey: 'dia', header: 'Día' },
    { id: 'trabajador', accessorFn: it => `${it.trabajador.codigo} ${it.trabajador.nombre}`, header: 'Trabajador', cell: x => { const it = x.row.original
      return <span><b className="font-semibold">{it.trabajador.nombre}</b><span className="block text-xs text-muted">{it.trabajador.codigo}{it.empresa ? ` · ${it.empresa}` : ''}</span></span> } },
    { accessorKey: 'tipo', header: 'Tipo', cell: x => <Pill tono={x.getValue() === 'he_no_programada' ? 'accent' : x.getValue() === 'fuera_geocerca' ? 'danger' : 'neutral'}>{TIPOS[x.getValue()] ?? x.getValue()}</Pill> },
    { accessorKey: 'detalle', header: 'Detalle', enableSorting: false, cell: x => { const it = x.row.original
      return <span className="block max-w-[340px]">{it.detalle}{it.alerta_pt && <span className="mt-1 block"><Pill tono="warning">{it.alerta_pt} (no bloquea)</Pill></span>}
        {it.observacion && <span className="block text-xs text-muted">Obs.: {it.observacion}</span>}</span> } },
    { accessorKey: 'estado', header: 'Estado', cell: x => { const it = x.row.original
      return <span className="flex flex-col items-start gap-0.5"><PillEstado estado={it.estado} />{it.destino && <span className="text-xs text-muted">→ {DESTINOS[it.destino]}</span>}</span> } },
    { id: 'acc', header: 'Acción', enableSorting: false, cell: x => x.row.original.accionable ? <Decision it={x.row.original} onHecho={() => setRecarga(n => n + 1)} /> : <span className="text-muted">—</span> },
  ], [])
  return <Pantalla>
    <PageHeader titulo={`Excepciones ${rol === 'jefe' ? 'de mi unidad' : ''}`.trim()} icon={Inbox}
      desc={<>Las HE preautorizadas en el horario se pagan solas. El exceso no programado llega aquí como <b>no autorizado</b>; regularizarlo es opcional.
        Destino por defecto: el de las reglas vigentes de cada empresa. Las alertas PT85/PT102 son informativas y no bloquean.</>} />
    <div className="grid gap-4 sm:grid-cols-3">
      <KpiCard icon={Inbox} label="Excepciones" value={resumen ? String(resumen.total) : '…'} sub="con los filtros actuales" />
      <KpiCard icon={Hourglass} label="Pendientes de decisión" value={resumen ? String(resumen.pendientes) : '…'} accent="amber" sub="accionables por usted" />
      <KpiCard icon={AlertTriangle} label="Fuera de geocerca" value={resumen ? String(resumen.fuera_geocerca) : '…'} accent="danger" sub="en el rango" />
    </div>
    <Card><Toolbar>
      <Field label="Desde"><input type="date" className="ds-input" value={desde} onChange={e => setDesde(e.target.value)} /></Field>
      <Field label="Hasta"><input type="date" className="ds-input" value={hasta} onChange={e => setHasta(e.target.value)} /></Field>
      <Field label="Tipo"><select className="ds-input" value={tipo} onChange={e => setTipo(e.target.value)}><option value="">Todos</option>
        {Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
      {rol !== 'jefe' && <Field label="Unidad"><select className="ds-input" value={unidad} onChange={e => setUnidad(e.target.value)}><option value="">Todas</option>
        {filtrarPorEmpresa(unidades, empresa, u => u.empresa_id).map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></Field>}
      <Button variant="primary" icon={Search} onClick={run}>Buscar</Button></Toolbar></Card>
    <DataTable data={[]} columns={cols} servidor={{ url: '/excepciones/bandeja', params, clave: 'exc', recarga, alRecibir: r => setResumen(r.resumen) }} vacio="Sin excepciones con esos filtros." tam={15}
      buscar="Buscar trabajador o tipo…" chips={<Chips label="Estado" valor={estado} onChange={setEstado} chips={[{ valor: 'pendiente', label: 'Pendientes' },
        { valor: 'aprobado', label: 'Aprobadas' }, { valor: 'rechazado', label: 'Rechazadas' }, { valor: 'informativo', label: 'Informativas' }, { valor: '', label: 'Todas' }]} />} />
  </Pantalla>
}

interface Saldo { id: number; codigo: string; nombre: string; unidad_id: number; saldo_horas: number; movimientos: number; creditos_por_vencer_30d: number; empresa_id?: number }

function Movimientos({ t }: { t: Saldo }) {
  const cols = useMemo<ColumnDef<any, any>[]>(() => [
    { accessorKey: 'fecha_movimiento', header: 'Fecha' },
    { accessorKey: 'tipo', header: 'Tipo', cell: x => x.getValue() === 'credito' ? <Pill tono="success"><TrendingUp size={12} />Crédito</Pill> : <Pill tono="danger"><TrendingDown size={12} />Débito</Pill> },
    { accessorKey: 'horas', header: 'Horas', cell: x => x.getValue().toFixed(2) },
    { accessorKey: 'saldo_anterior', header: 'Saldo anterior', cell: x => x.getValue().toFixed(2) },
    { accessorKey: 'saldo_nuevo', header: 'Saldo nuevo', cell: x => <b className="font-semibold">{x.getValue().toFixed(2)}</b> },
    { accessorKey: 'origen', header: 'Origen' },
    { accessorKey: 'fecha_expira', header: 'Vence', cell: x => x.getValue() ?? '—' },
  ], [])
  return <DataTable data={[]} columns={cols} servidor={{ url: `/banco-horas/historial/${t.id}`, clave: 'mov' }} vacio="Sin movimientos." buscar={false}
    titulo={`Movimientos · ${t.codigo} ${t.nombre} — saldo ${t.saldo_horas.toFixed(2)} h`} />
}

export function BolsaHoras({ rol }: { rol: string }) {
  const empresa = useEmpresaFiltro()
  const [sel, setSel] = useState<Saldo | null>(null)
  const [soloMov, setSoloMov] = useState<'si' | 'no'>(rol !== 'trabajador' ? 'si' : 'no')
  // S9: trabajador pide su propia fila paginada en la BD (page_size=1); gestores: tabla paginada en la BD.
  const c = useCarga(() => api<{ items: Saldo[] }>('/banco-horas/saldos?page=1&page_size=1').then(r => r.items), [])
  useEffect(() => { if (rol === 'trabajador') c.run().then(s => { if (s?.length) setSel(s[0]) }) }, [])
  if (rol === 'trabajador') return <Pantalla>
    <PageHeader titulo="Mi bolsa de horas" icon={PiggyBank} desc="Horas compensables acumuladas por horas extra destinadas a compensación." />
    {c.err && <Aviso tono="danger">{c.err}</Aviso>}
    {c.datos && !c.datos.length && <Aviso tono="neutral">No tienes una ficha de trabajador vinculada.</Aviso>}
    {sel && <><div className="grid gap-4 sm:grid-cols-2">
      <KpiCard icon={PiggyBank} label="Saldo disponible" value={`${sel.saldo_horas.toFixed(2)} h`} sub={`${sel.movimientos} movimientos`} />
      <KpiCard icon={Clock3} label="Por vencer (30 días)" value={`${sel.creditos_por_vencer_30d.toFixed(2)} h`} accent={sel.creditos_por_vencer_30d > 0 ? 'amber' : 'teal'} sub="créditos próximos a expirar" />
    </div><Movimientos t={sel} /></>}
  </Pantalla>
  const cols: ColumnDef<Saldo, any>[] = [
    { accessorKey: 'codigo', header: 'Código' }, { accessorKey: 'nombre', header: 'Trabajador' },
    { accessorKey: 'saldo_horas', header: 'Saldo (h)', cell: x => <b className={cn('font-semibold', x.getValue() < 0 && 'text-danger')}>{x.getValue().toFixed(2)}</b> },
    { accessorKey: 'creditos_por_vencer_30d', header: 'Por vencer 30 d (h)', cell: x => x.getValue() ? <Pill tono="warning">{x.getValue().toFixed(2)}</Pill> : '—' },
    { accessorKey: 'movimientos', header: 'Movimientos' },
    { id: 'acc', header: '', enableSorting: false, cell: x => <Button size="sm" variant={sel?.id === x.row.original.id ? 'primary' : 'secondary'} onClick={() => setSel(x.row.original)}>Ver movimientos</Button> },
  ]
  return <Pantalla>
    <PageHeader titulo={`Bolsa de horas ${rol === 'jefe' ? 'de mi unidad' : ''}`.trim()} icon={PiggyBank} desc="Saldos del banco de horas por trabajador y su historial de créditos/débitos." />
    <DataTable data={[]} columns={cols} servidor={{ url: '/banco-horas/saldos', params: { solo_con_movimientos: soloMov === 'si', empresa_id: empresa }, clave: 'bolsa' }} buscar="Código o nombre" vacio="Sin trabajadores con saldo."
      filaClase={s => sel?.id === s.id ? 'bg-accent-soft/60' : undefined}
      chips={<Chips label="Movimientos" valor={soloMov} onChange={setSoloMov} chips={[{ valor: 'si', label: 'Sólo con movimientos' }, { valor: 'no', label: 'Todos' }]} />} />
    {sel && <Movimientos t={sel} />}
  </Pantalla>
}
