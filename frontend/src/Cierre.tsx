import { useEffect, useMemo, useState } from 'react'
import { CalendarCheck, Check, CheckCircle2, History, Lock, LockOpen, Moon, RefreshCw, Save, TriangleAlert, X } from 'lucide-react'
import { api } from './api'
import { Aviso, Button, Card, Field, PageHeader, Pantalla, Pill, PillEstado, Toolbar, cn } from './ui'
import { DataTable, type ColumnDef } from './ui/DataTable'
import { confirmar, fallo, Modal, ok, pedirTexto } from './ui/feedback'
import { conEmpresa, filtrarPorEmpresa, guardarEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { fechaHora, mesLima as mesActual, nombreTrab, useCarga } from './ui/hooks'
import { ProgresoTrabajo, useTrabajo } from './Trabajos'

const soles = (v: any) => v === null || v === undefined || v === '' ? '—' : `S/ ${Number(v).toFixed(2)}`

function useEmpresas() {
  const [emps, setEmps] = useState<any[]>([])
  useEffect(() => { api('/empresas').then(setEmps).catch(() => {}) }, [])
  return emps
}
const SelEmpresa = ({ emps, valor, todas }: { emps: any[]; valor: string; todas?: boolean }) =>
  <Field label="Empresa"><select className="ds-input" value={valor} onChange={e => guardarEmpresa(e.target.value)}>
    {todas && <option value="">Todas</option>}{emps.map(e => <option key={e.id} value={e.id}>{e.codigo}</option>)}</select></Field>

/** Bono nocturno 3 AM (interno, no es el recargo legal): admin registra monto; otra persona RRHH/admin aprueba. */
export function Bonos({ rol, meId }: { rol: string; meId: number }) {
  const emps = useEmpresas(); const empresa = useEmpresaFiltro()
  const [periodo, setPeriodo] = useState(mesActual()); const [trabs, setTrabs] = useState<any[]>([])
  const [f, setF] = useState({ trabajador_id: '', cantidad: '1', monto: '', observacion: '' })
  const [hist, setHist] = useState<any[] | null>(null)
  const admin = rol === 'admin'
  const [recarga, setRecarga] = useState(0); const c = { run: () => setRecarga(n => n + 1) }
  useEffect(() => { api('/trabajadores').then(setTrabs).catch(() => {}) }, [])
  const guardar = async () => {
    try {
      await api('/bonos-nocturnos', { method: 'POST', body: { trabajador_id: Number(f.trabajador_id), periodo, cantidad: Number(f.cantidad),
        monto: f.monto === '' ? null : f.monto, observacion: f.observacion || null } })
      ok('Bono registrado: queda pendiente de aprobación por otra persona.'); setF({ ...f, monto: '', observacion: '' }); c.run()
    } catch (e) { fallo(e) }
  }
  const decidir = async (b: any, aprobar: boolean) => {
    const comentario = await pedirTexto({ titulo: aprobar ? 'Aprobar bono' : 'Rechazar bono', label: aprobar ? 'Comentario (opcional)' : 'Motivo del rechazo', opcional: aprobar, peligro: !aprobar, ok: aprobar ? 'Aprobar' : 'Rechazar' })
    if (comentario === null) return
    try { await api(`/bonos-nocturnos/${b.id}/decision`, { method: 'POST', body: { aprobar, comentario: comentario || undefined } }); ok(aprobar ? 'Bono aprobado.' : 'Bono rechazado.'); c.run() }
    catch (e) { fallo(e) }
  }
  const cols = useMemo<ColumnDef<any, any>[]>(() => [
    { id: 'trabajador_codigo', accessorFn: b => `${b.trabajador_codigo} ${b.trabajador}`, header: 'Trabajador' },
    { accessorKey: 'periodo', header: 'Periodo', cell: x => <span className="inline-flex items-center gap-1">{x.getValue()}{x.row.original.periodo_cerrado && <Lock size={12} aria-label="cerrado" />}</span> },
    { accessorKey: 'cantidad', header: 'Cantidad' }, { accessorKey: 'monto', header: 'Monto', cell: x => soles(x.getValue()) },
    { accessorKey: 'estado', header: 'Estado', cell: x => <PillEstado estado={x.getValue()} /> },
    { accessorKey: 'registrado_por_email', header: 'Registró' }, { accessorKey: 'aprobado_por_email', header: 'Aprobó', cell: x => x.getValue() || '' },
    { id: 'acc', header: '', enableSorting: false, cell: x => { const b = x.row.original
      return <span className="flex gap-1.5">{b.estado === 'registrado' && !b.periodo_cerrado && b.registrado_por !== meId && <>
        <Button size="sm" variant="primary" icon={Check} onClick={() => decidir(b, true)}>Aprobar</Button><Button size="sm" variant="danger" icon={X} onClick={() => decidir(b, false)}>Rechazar</Button></>}
        <Button size="sm" icon={History} onClick={() => api<any[]>(`/bonos-nocturnos/${b.id}/historial`).then(setHist).catch(fallo)}>Historial</Button></span> } },
  ], [meId])
  return <Pantalla>
    <PageHeader titulo="Bono nocturno 3 AM" icon={Moon} desc="Ingreso interno (no es el recargo nocturno legal). Admin registra cantidad y monto por trabajador y periodo; lo aprueba otra persona (RRHH/admin). Todo queda auditado. Periodo cerrado = no editable." />
    <Card><Toolbar><SelEmpresa emps={emps} valor={empresa} todas />
      <Field label="Periodo"><input type="month" className="ds-input" value={periodo} onChange={e => setPeriodo(e.target.value)} /></Field></Toolbar>
      {admin && <div className="mt-4 border-t border-border pt-4"><p className="m-0 mb-2 text-sm font-semibold">Registrar / corregir</p><Toolbar>
        <Field label="Trabajador"><select className="ds-input" value={f.trabajador_id} onChange={e => setF({ ...f, trabajador_id: e.target.value })}><option value="">Trabajador…</option>
          {filtrarPorEmpresa(trabs, empresa, t => t.empresa_id).map(t => <option key={t.id} value={t.id}>{nombreTrab(t)}</option>)}</select></Field>
        <Field label="Cantidad"><input type="number" min="0" className="ds-input w-24" value={f.cantidad} onChange={e => setF({ ...f, cantidad: e.target.value })} /></Field>
        <Field label="Monto S/"><input type="number" min="0" step="0.01" className="ds-input w-28" value={f.monto} onChange={e => setF({ ...f, monto: e.target.value })} /></Field>
        <Field label="Observación"><input className="ds-input" value={f.observacion} onChange={e => setF({ ...f, observacion: e.target.value })} /></Field>
        <Button variant="primary" icon={Save} disabled={!f.trabajador_id} onClick={guardar}>Guardar</Button></Toolbar></div>}
    </Card>
    <DataTable data={[]} columns={cols} servidor={{ url: '/bonos-nocturnos', params: { periodo, empresa_id: empresa }, clave: 'bonos', recarga }} vacio="Sin bonos registrados en el periodo." />
    <Modal abierto={!!hist} onClose={() => setHist(null)} titulo="Historial del bono">
      <ol className="m-0 grid list-none gap-2 p-0">{(hist ?? []).map((h, i) => <li key={i} className="rounded-ctl border border-border p-2 text-sm">
        <span className="text-xs text-muted">{fechaHora(h.ts)}</span><br /><b>{h.accion}</b> — cant. {h.cantidad} — {soles(h.monto)} — <PillEstado estado={h.estado} />{h.comentario ? ` — ${h.comentario}` : ''}</li>)}</ol>
    </Modal>
  </Pantalla>
}

const ETIQUETAS: Record<string, string> = { he_sin_decidir: 'HE sin decidir', excepciones_pendientes: 'Excepciones pendientes (fuera de geocerca)',
  marcas_incompletas: 'Marcas impares/incompletas', bonos_sin_aprobar: 'Bonos 3 AM sin aprobar' }

/** Cierre de periodo (mes calendario por día operativo): checklist, confirmación, cierre y reapertura (sólo admin). */
export function Periodos({ rol }: { rol: string }) {
  const emps = useEmpresas(); const global = useEmpresaFiltro()
  const empresa = global || (emps[0] ? String(emps[0].id) : '')
  const [periodo, setPeriodo] = useState(mesActual())
  const [ck, setCk] = useState<any>(null); const [err, setErr] = useState('')
  const [abierto, setAbierto] = useState<string | null>(null)
  const { trabajo, seguir, limpiar } = useTrabajo()
  const h = useCarga(() => empresa ? api<any[]>(`/periodos/historial?empresa_id=${empresa}`) : Promise.resolve([]), [empresa])
  const cargar = () => {
    if (!empresa) return
    setErr('')
    api(`/periodos/checklist?empresa_id=${empresa}&periodo=${periodo}`).then(setCk).catch(e => setErr(e.message))
    h.run()
  }
  useEffect(() => { cargar() }, [empresa, periodo])
  const pend = ck?.total_pendientes ?? 0
  const cerrar = async () => {
    const ok1 = await confirmar({ titulo: `¿Cerrar ${ck.periodo}?`, peligro: pend > 0, ok: `Sí, cerrar${pend > 0 ? ' con pendientes' : ''}`,
      mensaje: `${pend > 0 ? `Hay ${pend} pendiente(s). Si cierra igual, quedarán congelados tal como están. ` : 'Sin pendientes. '}Después no se podrán modificar marcas, regularizaciones ni bonos.` })
    if (!ok1) return
    try { await api('/periodos/cerrar', { method: 'POST', body: { empresa_id: Number(empresa), periodo, confirmar: true } }); ok(`Periodo ${periodo} cerrado.`); cargar() }
    catch (e) { fallo(e) }
  }
  const reabrir = async (c: any) => {
    const razon = await pedirTexto({ titulo: `Reabrir ${c.periodo}`, label: 'Motivo de la reapertura (mínimo 10 caracteres)', min: 10, ok: 'Reabrir', peligro: true })
    if (!razon) return
    try { await api(`/periodos/reabrir/${c.id}`, { method: 'POST', body: { razon_reapertura: razon } }); ok(`Periodo ${c.periodo} reabierto.`); cargar() }
    catch (e) { fallo(e) }
  }
  const recalcular = async () => {
    limpiar()
    try {
      const r = await api(`/periodos/recalcular?empresa_id=${empresa}&periodo=${periodo}`, { method: 'POST' })
      if (r.trabajo) { const fin = await seguir(r.trabajo); fin.estado === 'ok' ? ok(`Recalculo de ${periodo} completado.`) : fallo(`Recalculo con error: ${fin.error}`) }
      else ok(`Recalculados ${r.trabajadores_recalculados} trabajador(es).`)
      cargar()
    } catch (e) { fallo(e) }
  }
  const cols: ColumnDef<any, any>[] = [
    { accessorKey: 'periodo', header: 'Periodo' }, { accessorKey: 'estado', header: 'Estado', cell: x => <Pill tono={x.getValue() === 'cerrado' ? 'neutral' : 'warning'}>{x.getValue()}</Pill> },
    { accessorKey: 'cerrado_en', header: 'Cerrado', cell: x => fechaHora(x.getValue()) },
    { accessorKey: 'razon_reapertura', header: 'Reapertura', cell: x => x.getValue() || '' },
    { id: 'acc', header: '', enableSorting: false, cell: x => rol === 'admin' && x.row.original.estado === 'cerrado' && <Button size="sm" variant="danger" icon={LockOpen} onClick={() => reabrir(x.row.original)}>Reabrir</Button> },
  ]
  return <Pantalla>
    <PageHeader titulo="Cierre de periodo" icon={CalendarCheck} desc="Periodo = mes calendario por día operativo. Cerrado: se bloquean marcas, regularizaciones y bonos (409). Exportación FINAL a Planilla Core sólo con periodo cerrado. Reabrir: sólo admin, con motivo (auditado).">
      {ck && <Pill tono={ck.cerrado ? 'neutral' : 'warning'}>{ck.cerrado ? <><Lock size={12} />CERRADO</> : 'ABIERTO'}</Pill>}
    </PageHeader>
    <Card><Toolbar><SelEmpresa emps={emps} valor={empresa} />
      <Field label="Periodo"><input type="month" className="ds-input" value={periodo} onChange={e => setPeriodo(e.target.value)} /></Field>
      <Button icon={RefreshCw} onClick={cargar}>Actualizar</Button>
      {ck && !ck.cerrado && <Button icon={RefreshCw} onClick={recalcular}>Recalcular periodo</Button>}
      {ck && !ck.cerrado && <Button variant="primary" icon={Lock} onClick={cerrar}>Cerrar periodo…</Button>}
    </Toolbar></Card>
    <ProgresoTrabajo t={trabajo} />
    {err && <Aviso tono="danger">{err}</Aviso>}
    {ck && <Card>
      <p className="m-0 mb-3 text-sm font-semibold">Checklist {ck.periodo} <span className="font-normal text-muted">({ck.desde} a {ck.hasta})</span></p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Object.entries(ck.conteos).map(([k, v]: any) =>
        <button type="button" key={k} disabled={!v} onClick={() => setAbierto(abierto === k ? null : k)}
          className={cn('flex items-center gap-3 rounded-card border p-3 text-left', v ? 'border-warning/40 bg-warning/10 cursor-pointer' : 'border-border bg-surface-2')}>
          {v ? <TriangleAlert className="text-warning" size={22} /> : <CheckCircle2 className="text-success" size={22} />}
          <span><span className="block text-xs text-muted">{ETIQUETAS[k] || k}</span><b className="text-xl">{v}</b></span></button>)}</div>
      {abierto && ck[abierto] && <pre className="mt-3 max-h-64 overflow-auto rounded-ctl bg-surface-2 p-3 text-xs">{JSON.stringify(ck[abierto], null, 1)}</pre>}
    </Card>}
    <DataTable data={h.datos ?? []} columns={cols} cargando={h.cargando} error={h.err} buscar={false} titulo="Historial de cierres" vacio="Sin cierres registrados." />
  </Pantalla>
}
