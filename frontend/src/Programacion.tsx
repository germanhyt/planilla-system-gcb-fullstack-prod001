import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { yupResolver } from '@hookform/resolvers/yup'
import * as yup from 'yup'
import { CalendarPlus, Timer, Trash2 } from 'lucide-react'
import { api } from './api'
import { Button, Card, Field, PageHeader, Pantalla, Toolbar } from './ui'
import { DataTable, type ColumnDef } from './ui/DataTable'
import { confirmar, fallo, ok } from './ui/feedback'
import { filtrarPorEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { hoyLima as hoy, nombreTrab } from './ui/hooks'

const sumarDias = (d: string, n: number) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10) }
const esquema = yup.object({
  trabajador_id: yup.string().required('Seleccione un trabajador'),
  dia: yup.string().required('Indique el día'),
  horas: yup.number().typeError('Número de horas').min(0.25, 'Mínimo 0.25 h').max(12, 'Máximo 12 h').required(),
  motivo: yup.string().default(''),
})
type Form = yup.InferType<typeof esquema>

/** Sprint 4: el jefe programa (preautoriza) horas extra por trabajador y día operativo.
 * Sólo lo programado se paga automáticamente; el exceso no programado llega a la bandeja como no autorizado. */
export function HEProgramadas({ rol }: { rol: string }) {
  const empresa = useEmpresaFiltro()
  const [desde, setDesde] = useState(hoy()); const [hasta, setHasta] = useState(sumarDias(hoy(), 13))
  const [trabs, setTrabs] = useState<any[]>([])
  const gestor = rol !== 'trabajador'
  const [recarga, setRecarga] = useState(0); const recargar = () => setRecarga(n => n + 1)
  useEffect(() => { if (gestor) api('/trabajadores').then(setTrabs).catch(() => {}) }, [])
  const { register, handleSubmit, formState: { errors, isSubmitting }, reset } = useForm({ resolver: yupResolver(esquema), defaultValues: { trabajador_id: '', dia: hoy(), horas: 2, motivo: '' } })
  const guardar = async (f: Form) => {
    try {
      await api('/he-programadas', { method: 'POST', body: { trabajador_id: Number(f.trabajador_id), dia: f.dia, horas: Number(f.horas), motivo: f.motivo || null } })
      ok('Horas extra programadas.'); reset({ ...f, motivo: '' }); recargar()
    } catch (e) { fallo(e) }
  }
  const anular = async (id: number) => {
    if (!await confirmar({ titulo: '¿Anular esta programación?', mensaje: 'Las horas dejarán de pagarse automáticamente.', peligro: true, ok: 'Anular' })) return
    try { await api(`/he-programadas/${id}`, { method: 'DELETE' }); ok('Programación anulada.'); recargar() } catch (e) { fallo(e) }
  }
  const trabsVis = filtrarPorEmpresa(trabs, empresa, t => t.empresa_id)
  const cols = useMemo<ColumnDef<any, any>[]>(() => [
    { accessorKey: 'dia', header: 'Día' },
    { id: 'trabajador', accessorFn: h => nombreTrab(h.trabajador), header: 'Trabajador' },
    { accessorKey: 'horas', header: 'Horas', cell: x => <b className="font-semibold">{x.getValue()} h</b> },
    { accessorKey: 'motivo', header: 'Motivo', cell: x => x.getValue() || <span className="text-muted">—</span> },
    ...(gestor ? [{ id: 'acc', header: '', enableSorting: false, cell: (x: any) => <Button size="sm" variant="danger" icon={Trash2} onClick={() => anular(x.row.original.id)}>Anular</Button> }] : []),
  ], [gestor])
  return <Pantalla>
    <PageHeader titulo="Horas extra programadas" icon={Timer}
      desc={<>Sólo las horas extra programadas aquí se pagan automáticamente (25 % las 2 primeras, 35 % el resto). El exceso no programado llega a la bandeja como <b>no autorizado</b>.</>} />
    {gestor && <Card><form onSubmit={handleSubmit(guardar)} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end" noValidate>
      <Field label="Trabajador" error={errors.trabajador_id?.message}><select className="ds-input" {...register('trabajador_id')}>
        <option value="">—</option>{trabsVis.map(t => <option key={t.id} value={t.id}>{nombreTrab(t)}</option>)}</select></Field>
      <Field label="Día operativo" error={errors.dia?.message}><input type="date" className="ds-input" {...register('dia')} /></Field>
      <Field label="Horas" error={errors.horas?.message}><input type="number" step="0.25" className="ds-input" {...register('horas')} /></Field>
      <Field label="Motivo"><input className="ds-input" {...register('motivo')} /></Field>
      <Button type="submit" variant="primary" icon={CalendarPlus} disabled={isSubmitting}>Programar</Button>
    </form></Card>}
    <DataTable data={[]} columns={cols} numerar servidor={{ url: '/he-programadas', clave: 'he', recarga, params: { desde, hasta, empresa_id: empresa } }}
      buscar="Buscar trabajador o motivo" vacio="No hay horas extra programadas en el rango."
      titulo={<Toolbar>
        <Field label="Desde"><input type="date" className="ds-input" value={desde} onChange={e => setDesde(e.target.value)} /></Field>
        <Field label="Hasta"><input type="date" className="ds-input" value={hasta} onChange={e => setHasta(e.target.value)} /></Field></Toolbar>} />
  </Pantalla>
}
