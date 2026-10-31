import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { yupResolver } from '@hookform/resolvers/yup'
import * as yup from 'yup'
import { Database, Pencil, Plus, Power } from 'lucide-react'
import { api } from './api'
import { Button, PageHeader, Pantalla, Pill } from './ui'
import { Chips, DataTable, type ColumnDef } from './ui/DataTable'
import { confirmar, fallo, Modal, ok } from './ui/feedback'
import { useEmpresaFiltro } from './ui/empresaFiltro'

export type Campo = { k: string; label: string; tipo?: 'text' | 'number' | 'date' | 'time' | 'checkbox' | 'select'; opciones?: string; req?: boolean }
type Props = { titulo: string; ruta: string; campos: Campo[]; puedeEscribir: boolean }

/** Esquema yup derivado de los campos (obligatorios y numéricos). */
export function esquemaCampos(campos: Campo[]) {
  const forma: Record<string, yup.AnySchema> = {}
  for (const c of campos) {
    let s: yup.AnySchema = c.tipo === 'checkbox' ? yup.boolean() : yup.string().nullable()
    if (c.tipo === 'number') s = (s as yup.StringSchema).test('num', 'Debe ser un número', v => v === null || v === undefined || v === '' || !isNaN(Number(v)))
    if (c.req && c.tipo !== 'checkbox') s = (s as yup.StringSchema).required('Obligatorio')
    forma[c.k] = s
  }
  return yup.object(forma)
}

function FormCrud({ campos, inicial, ops, onGuardar, onCancelar }: { campos: Campo[]; inicial: any; ops: Record<string, any[]>; onGuardar: (v: any) => Promise<void>; onCancelar: () => void }) {
  const esquema = useMemo(() => esquemaCampos(campos), [campos])
  const def = Object.fromEntries(campos.map(c => [c.k, c.tipo === 'checkbox' ? !!inicial[c.k] : inicial[c.k] == null ? '' : String(inicial[c.k])]))
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<any>({ resolver: yupResolver(esquema) as any, defaultValues: def })
  return <form onSubmit={handleSubmit(onGuardar)} noValidate className="grid gap-3 sm:grid-cols-2">
    {campos.map(c => { const e = (errors as any)[c.k]?.message as string | undefined
      if (c.tipo === 'checkbox') return <label key={c.k} className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4" {...register(c.k)} />{c.label}</label>
      return <label key={c.k} className="flex flex-col gap-1 text-xs font-medium text-muted">{c.label}{c.req && ' *'}
        {c.tipo === 'select' ? <select className="ds-input" {...register(c.k)}><option value="">—</option>
          {(ops[c.k] || []).map(o => <option key={o.id} value={o.id}>{o.codigo || o.nombre || o.razon_social || o.email}</option>)}</select>
          : <input className="ds-input" type={c.tipo || 'text'} step={c.tipo === 'number' ? 'any' : undefined} {...register(c.k)} />}
        {e && <span className="font-normal text-danger">{e}</span>}</label> })}
    <div className="flex justify-end gap-2 sm:col-span-2"><Button onClick={onCancelar}>Cancelar</Button><Button type="submit" variant="primary" disabled={isSubmitting}>Guardar</Button></div>
  </form>
}

export function Crud({ titulo, ruta, campos, puedeEscribir }: Props) {
  const empresa = useEmpresaFiltro()
  const [recarga, setRecarga] = useState(0)
  const [form, setForm] = useState<any | null>(null)
  const [ops, setOps] = useState<Record<string, any[]>>({})
  const [act, setAct] = useState<'' | 'si' | 'no'>('')
  const cargar = () => setRecarga(n => n + 1)
  useEffect(() => {
        campos.filter(c => c.opciones).forEach(c => api(c.opciones!).then(d => setOps(o => ({ ...o, [c.k]: d }))).catch(() => {}))
  }, [ruta])
  const etiqueta = (c: Campo, v: any) => {
    const o = ops[c.k]?.find(x => x.id === v)
    return o ? (o.codigo || o.nombre || o.razon_social || o.id) : String(v ?? '')
  }
  const guardar = async (vals: any) => {
    const body: any = {}
    for (const c of campos) {
      let v = vals[c.k]
      if (v === '' || v === undefined) v = null
      if (v !== null && (c.tipo === 'number' || c.tipo === 'select')) v = Number(v)
      body[c.k] = c.tipo === 'checkbox' ? !!v : v
    }
    if ('activo' in (form || {})) body.activo = form.activo
    try {
      await api(form.id ? `${ruta}/${form.id}` : ruta, { method: form.id ? 'PUT' : 'POST', body })
      ok(form.id ? 'Registro actualizado.' : 'Registro creado.'); setForm(null); cargar()
    } catch (e) { fallo(e) }
  }
  const borrar = async (id: number) => {
    if (!await confirmar({ titulo: '¿Desactivar registro?', peligro: true, ok: 'Desactivar' })) return
    try { await api(`${ruta}/${id}`, { method: 'DELETE' }); ok('Registro desactivado.'); cargar() } catch (e) { fallo(e) }
  }
  const tieneActivo = true // todos los maestros usan baja lógica (activo)
  const cols = useMemo<ColumnDef<any, any>[]>(() => [
    ...campos.slice(0, 7).map(c => ({ id: c.k, accessorFn: (f: any) => c.tipo === 'select' ? etiqueta(c, f[c.k]) : f[c.k], header: c.label,
      cell: (x: any) => c.tipo === 'checkbox' ? <Pill tono={x.getValue() ? 'success' : 'neutral'}>{x.getValue() ? 'Sí' : 'No'}</Pill> : String(x.getValue() ?? '') }) as ColumnDef<any, any>),
    ...(tieneActivo && !campos.some(c => c.k === 'activo') ? [{ accessorKey: 'activo', header: 'Estado', cell: (x: any) => <Pill tono={x.getValue() === false ? 'neutral' : 'success'}>{x.getValue() === false ? 'Inactivo' : 'Activo'}</Pill> } as ColumnDef<any, any>] : []),
    ...(puedeEscribir ? [{ id: 'acc', header: '', enableSorting: false, cell: (x: any) => <span className="flex gap-1.5">
      <Button size="sm" icon={Pencil} onClick={() => setForm(x.row.original)}>Editar</Button>
      <Button size="sm" variant="danger" icon={Power} onClick={() => borrar(x.row.original.id)}>Desactivar</Button></span> } as ColumnDef<any, any>] : []),
  ], [campos, ops, puedeEscribir, tieneActivo])
    return <Pantalla>
    <PageHeader titulo={titulo} icon={Database}>{puedeEscribir && <Button variant="primary" icon={Plus} onClick={() => setForm({})}>Nuevo</Button>}</PageHeader>
    <DataTable data={[]} columns={cols} servidor={{ url: ruta, clave: ruta.slice(1), recarga, params: { incluir_inactivos: act !== 'si', activo: act === '' ? '' : act === 'si', empresa_id: ruta === '/trabajadores' || ruta === '/unidades' ? empresa : '' } }} tam={50} vacio="Sin registros."
      chips={tieneActivo ? <Chips label="Estado" valor={act} onChange={setAct} chips={[{ valor: '', label: 'Todos' }, { valor: 'si', label: 'Activos' }, { valor: 'no', label: 'Inactivos' }]} /> : undefined} />
    <Modal abierto={!!form} onClose={() => setForm(null)} titulo={form?.id ? `Editar · ${titulo}` : `Nuevo · ${titulo}`} ancho="max-w-2xl">
      {form && <FormCrud campos={campos} inicial={form} ops={ops} onGuardar={guardar} onCancelar={() => setForm(null)} />}
    </Modal>
  </Pantalla>
}
