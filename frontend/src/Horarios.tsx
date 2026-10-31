import { useEffect, useState } from 'react'
import { CalendarClock, CalendarDays, Minus, Plus, Save, Trash2 } from 'lucide-react'
import { api } from './api'
import { Aviso, Button, Card, Field, PageHeader, Pantalla, Pill, Toolbar, Vacio, cn } from './ui'
import { DataTable, type ColumnDef } from './ui/DataTable'
import { confirmar, fallo, ok } from './ui/feedback'
import { filtrarPorEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { hoyLima as hoy, nombreTrab } from './ui/hooks'

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const sumar = (d: string, n: number) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }
const lunes = (d: string) => { const x = new Date(d + 'T12:00:00'); return sumar(d, -((x.getDay() + 6) % 7)) }

/** Sprint 4: horario asignado por trabajador (patrón de 1..N semanas con vigencia) y calendario resuelto. */
export function Horarios({ rol }: { rol: string }) {
  const empresa = useEmpresaFiltro()
  const [trabs, setTrabs] = useState<any[]>([]); const [plantillas, setPlantillas] = useState<any[]>([])
  const [tid, setTid] = useState(''); const [rec, setRec] = useState(0); const [cal, setCal] = useState<any>(null)
  const [desde, setDesde] = useState(lunes(hoy())); const [hasta, setHasta] = useState('')
  const [patron, setPatron] = useState<string[][]>([Array(7).fill('')]); const [nota, setNota] = useState(''); const [err, setErr] = useState('')
  const gestor = rol !== 'trabajador'
  useEffect(() => {
    if (gestor) { api('/trabajadores').then(setTrabs).catch(() => {}); api('/turnos-plantilla').then(setPlantillas).catch(() => {}) }
  }, [])
  const t = trabs.find(x => String(x.id) === tid)
  const propias = plantillas.filter(p => t && p.unidad_id === t.unidad_id && p.activo)
  const cargar = () => {
    if (!tid) return
    setRec(x => x + 1)  // S9: la tabla de asignaciones pagina en la BD
    api(`/asignaciones-horario/calendario?trabajador_id=${tid}&desde=${lunes(hoy())}&hasta=${sumar(lunes(hoy()), 27)}`).then(setCal).catch(() => setCal(null))
  }
  useEffect(() => { setErr(''); cargar() }, [tid])
  const guardar = async () => {
    try {
      await api('/asignaciones-horario', { method: 'POST', body: { trabajador_id: Number(tid), vigente_desde: desde, vigente_hasta: hasta || null,
        patron: patron.map(s => s.map(v => v ? Number(v) : null)), nota: nota || null } })
      ok('Horario asignado.'); cargar()
    } catch (e) { fallo(e) }
  }
  const eliminar = async (id: number) => {
    if (!await confirmar({ titulo: '¿Eliminar esta asignación?', peligro: true, ok: 'Eliminar' })) return
    try { await api(`/asignaciones-horario/${id}`, { method: 'DELETE' }); ok('Asignación eliminada.'); cargar() } catch (e) { fallo(e) }
  }
  const nombre = (id: number | null) => id ? (plantillas.find(p => p.id === id)?.nombre ?? `#${id}`) : 'Descanso'
  if (!gestor) return <Pantalla><PageHeader titulo="Horarios" icon={CalendarClock} /><Vacio texto="Consulte su horario con su jefe." icon={CalendarDays} /></Pantalla>
  const cols: ColumnDef<any, any>[] = [
    { accessorKey: 'vigente_desde', header: 'Desde' }, { accessorKey: 'vigente_hasta', header: 'Hasta', cell: x => x.getValue() ?? <Pill tono="accent">abierta</Pill> },
    { accessorKey: 'patron', header: 'Patrón', enableSorting: false, cell: x => <span className="grid gap-0.5 text-xs">{x.getValue().map((s: (number | null)[], i: number) => <span key={i}><b>S{i + 1}:</b> {s.map(nombre).join(' · ')}</span>)}</span> },
    { accessorKey: 'nota', header: 'Nota' },
    { id: 'acc', header: '', enableSorting: false, cell: x => <Button size="sm" variant="danger" icon={Trash2} onClick={() => eliminar(x.row.original.id)}>Eliminar</Button> },
  ]
  return <Pantalla>
    <PageHeader titulo="Asignación de horarios" icon={CalendarClock} desc="El patrón rota cada semana desde la semana de inicio. Una programación semanal explícita tiene prioridad. Si el turno no define refrigerio se aplica el del tipo de contrato." />
    <Card><Toolbar><Field label="Trabajador" className="min-w-72"><select className="ds-input" value={tid} onChange={e => setTid(e.target.value)}><option value="">—</option>
      {filtrarPorEmpresa(trabs, empresa, x => x.empresa_id).map(x => <option key={x.id} value={x.id}>{nombreTrab(x)}</option>)}</select></Field></Toolbar></Card>
    {err && <Aviso tono="danger">{err}</Aviso>}
    {!t && <Vacio texto="Seleccione un trabajador para ver y asignar su horario." icon={CalendarDays} />}
    {t && <>
      <Card>
        <p className="m-0 mb-3 text-sm font-semibold">Nueva asignación</p>
        <Toolbar>
          <Field label="Vigente desde"><input type="date" className="ds-input" value={desde} onChange={e => setDesde(e.target.value)} /></Field>
          <Field label="Hasta (opcional)"><input type="date" className="ds-input" value={hasta} onChange={e => setHasta(e.target.value)} /></Field>
          <Field label="Nota"><input className="ds-input" value={nota} onChange={e => setNota(e.target.value)} /></Field>
        </Toolbar>
        <div className="mt-3 overflow-x-auto"><table className="w-full border-separate border-spacing-1 text-sm"><thead><tr><th className="text-left text-xs text-muted">Semana</th>{DIAS.map(d => <th key={d} className="text-left text-xs text-muted">{d}</th>)}</tr></thead><tbody>
          {patron.map((s, i) => <tr key={i}><td className="font-semibold">S{i + 1}</td>{s.map((v, j) => <td key={j}>
            <select aria-label={`Semana ${i + 1} ${DIAS[j]}`} className={cn('ds-input min-w-28', !v && 'text-muted')} value={v} onChange={e => setPatron(patron.map((ss, ii) => ii !== i ? ss : ss.map((vv, jj) => jj === j ? e.target.value : vv)))}>
              <option value="">Descanso</option>{propias.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select></td>)}</tr>)}
        </tbody></table></div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" icon={Plus} onClick={() => setPatron([...patron, Array(7).fill('')])} disabled={patron.length >= 8}>Semana</Button>
          <Button size="sm" icon={Minus} onClick={() => setPatron(patron.slice(0, -1))} disabled={patron.length <= 1}>Semana</Button>
          <span className="flex-1" /><Button variant="primary" icon={Save} onClick={guardar}>Asignar</Button></div>
      </Card>
      <DataTable data={[]} columns={cols} buscar={false} servidor={{ url: '/asignaciones-horario', params: { trabajador_id: tid }, clave: 'asig', recarga: rec }} titulo="Asignaciones" vacio="Sin asignaciones." />
      {cal && <Card>
        <p className="m-0 mb-3 text-sm font-semibold">Próximas 4 semanas <span className="font-normal text-muted">({cal.contrato}, jornada {cal.jornada_diaria_min} min)</span></p>
        <div className="grid grid-cols-7 gap-1.5 text-xs">{DIAS.map(d => <div key={d} className="px-1 font-semibold text-muted">{d}</div>)}
          {cal.dias.map((d: any) => <div key={d.dia} title={d.origen} className={cn('min-h-16 rounded-ctl border p-1.5', d.inicio ? 'border-accent/30 bg-accent-soft' : 'border-border bg-surface-2 text-muted')}>
            <div className="font-semibold">{d.dia.slice(8)}</div>
            {d.inicio ? <><div className="truncate">{d.plantilla}</div><div>{d.inicio}–{d.fin}</div><div className="text-muted">{d.horas_programadas} h</div></> : <div>Descanso</div>}
          </div>)}</div>
      </Card>}
    </>}
  </Pantalla>
}
