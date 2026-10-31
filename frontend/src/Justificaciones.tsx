import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { yupResolver } from '@hookform/resolvers/yup'
import * as yup from 'yup'
import { Check, FileText, Send, Undo2, X } from 'lucide-react'
import { api } from './api'
import { Button, Card, Field, PageHeader, Pantalla, PillEstado } from './ui'
import { Chips, DataTable, type ColumnDef } from './ui/DataTable'
import { confirmar, fallo, ok, pedirTexto } from './ui/feedback'
import { filtrarPorEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { hoyLima as hoy, nombreTrab, useCarga } from './ui/hooks'

const MOTIVOS: [string, string][] = [['permiso', 'Permiso'], ['licencia_medica', 'Licencia médica'], ['vacaciones', 'Vacaciones'], ['otro', 'Otro']]
const esquema = yup.object({
  trabajador_id: yup.string().required('Seleccione un trabajador'),
  dia: yup.string().required('Indique el día'),
  motivo: yup.string().oneOf(MOTIVOS.map(m => m[0])).required(),
  descripcion: yup.string().max(500, 'Máximo 500 caracteres').default(''),
  adjunto_url: yup.string().url('Debe ser un enlace http(s) válido').default(''),
})
type Form = yup.InferType<typeof esquema>
type Estado = '' | 'pendiente' | 'aprobada' | 'rechazada'

/** Sprint 4: justificación de faltas. Trabajador solicita; jefe/RRHH aprueba o rechaza (o registra directo). */
export function Justificaciones({ rol }: { rol: string }) {
  const gestor = rol !== 'trabajador'
  const empresa = useEmpresaFiltro()
  const [trabs, setTrabs] = useState<any[]>([]); const [filtro, setFiltro] = useState<Estado>(gestor ? 'pendiente' : '')
  const c = useCarga(() => api<any[]>(`/justificaciones${filtro ? `?estado=${filtro}` : ''}`), [filtro])
  useEffect(() => { c.run() }, [filtro])
  const { register, handleSubmit, setValue, reset, getValues, formState: { errors, isSubmitting } } = useForm({ resolver: yupResolver(esquema),
    defaultValues: { trabajador_id: '', dia: hoy(), motivo: 'permiso', descripcion: '', adjunto_url: '' } })
  useEffect(() => {
    if (gestor) api('/trabajadores').then(setTrabs).catch(() => {})
    else api('/me/trabajador').then((t: any) => t?.id && setValue('trabajador_id', String(t.id))).catch(() => {})
  }, [])
  const enviar = async (f: Form) => {
    try {
      await api('/justificaciones', { method: 'POST', body: { ...f, trabajador_id: Number(f.trabajador_id), descripcion: f.descripcion || null, adjunto_url: f.adjunto_url || null } })
      ok(gestor ? 'Justificación registrada (aprobada).' : 'Solicitud enviada a su jefe.'); reset({ ...getValues(), descripcion: '', adjunto_url: '' }); c.run()
    } catch (e) { fallo(e) }
  }
  const decidir = async (id: number, aprobar: boolean) => {
    let comentario: string | null = null
    if (!aprobar) { comentario = await pedirTexto({ titulo: 'Rechazar justificación', label: 'Motivo del rechazo', opcional: true, ok: 'Rechazar', peligro: true }); if (comentario === null) return }
    try { await api(`/justificaciones/${id}/decidir`, { method: 'POST', body: { aprobar, comentario: comentario || null } }); ok(aprobar ? 'Justificación aprobada.' : 'Justificación rechazada.'); c.run() } catch (e) { fallo(e) }
  }
  const retirar = async (id: number) => {
    if (!await confirmar({ titulo: '¿Retirar la solicitud?', ok: 'Retirar' })) return
    try { await api(`/justificaciones/${id}`, { method: 'DELETE' }); ok('Solicitud retirada.'); c.run() } catch (e) { fallo(e) }
  }
  const cols = useMemo<ColumnDef<any, any>[]>(() => [
    { accessorKey: 'dia', header: 'Día' },
    ...(gestor ? [{ id: 't', accessorFn: (j: any) => nombreTrab(j.trabajador), header: 'Trabajador' }] : []),
    { accessorKey: 'motivo', header: 'Motivo', cell: x => MOTIVOS.find(m => m[0] === x.getValue())?.[1] ?? x.getValue() },
    { accessorKey: 'descripcion', header: 'Detalle', cell: x => <span>{x.getValue() || <span className="text-muted">—</span>}
      {x.row.original.adjunto_url && <> · <a href={x.row.original.adjunto_url} target="_blank" rel="noreferrer">sustento</a></>}</span> },
    { accessorKey: 'estado', header: 'Estado', cell: x => <span className="flex flex-col items-start gap-0.5"><PillEstado estado={x.getValue()} />
      {x.row.original.comentario_decision && <span className="text-xs text-muted">{x.row.original.comentario_decision}</span>}</span> },
    { id: 'acc', header: '', enableSorting: false, cell: x => { const j = x.row.original; if (j.estado !== 'pendiente') return null
      return gestor ? <span className="flex gap-1.5"><Button size="sm" variant="primary" icon={Check} onClick={() => decidir(j.id, true)}>Aprobar</Button>
        <Button size="sm" variant="danger" icon={X} onClick={() => decidir(j.id, false)}>Rechazar</Button></span>
        : <Button size="sm" icon={Undo2} onClick={() => retirar(j.id)}>Retirar</Button> } },
  ], [gestor])
  const lista = filtrarPorEmpresa(c.datos ?? [], empresa, j => j.trabajador?.empresa_id)
  return <Pantalla>
    <PageHeader titulo={gestor ? 'Justificación de faltas' : 'Justificar una falta'} icon={FileText}
      desc={gestor ? 'Registre justificaciones (quedan aprobadas) o decida las solicitudes de su equipo.' : 'Su jefe revisará la solicitud. Puede adjuntar un enlace al sustento.'} />
    <Card><form onSubmit={handleSubmit(enviar)} noValidate className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {gestor && <Field label="Trabajador" error={errors.trabajador_id?.message}><select className="ds-input" {...register('trabajador_id')}><option value="">—</option>
        {filtrarPorEmpresa(trabs, empresa, t => t.empresa_id).map(t => <option key={t.id} value={t.id}>{nombreTrab(t)}</option>)}</select></Field>}
      <Field label="Día" error={errors.dia?.message}><input type="date" className="ds-input" {...register('dia')} /></Field>
      <Field label="Motivo"><select className="ds-input" {...register('motivo')}>{MOTIVOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
      <Field label="Detalle" error={errors.descripcion?.message}><input className="ds-input" {...register('descripcion')} /></Field>
      <Field label="Enlace a sustento (opcional)" error={errors.adjunto_url?.message}><input className="ds-input" placeholder="https://…" {...register('adjunto_url')} /></Field>
      <div className="flex items-end"><Button type="submit" variant="primary" icon={Send} disabled={isSubmitting} className="w-full sm:w-auto">{gestor ? 'Registrar' : 'Enviar solicitud'}</Button></div>
    </form>{!gestor && errors.trabajador_id && <p className="m-0 mt-2 text-xs text-danger">Su usuario no tiene ficha de trabajador asociada.</p>}</Card>
    <DataTable data={lista} columns={cols} cargando={c.cargando} error={c.err} reintentar={c.run} vacio="No hay justificaciones con este filtro."
      chips={<Chips label="Estado" valor={filtro} onChange={setFiltro} chips={[{ valor: 'pendiente', label: 'Pendientes' }, { valor: 'aprobada', label: 'Aprobadas' },
        { valor: 'rechazada', label: 'Rechazadas' }, { valor: '', label: 'Todas' }]} />} />
  </Pantalla>
}
