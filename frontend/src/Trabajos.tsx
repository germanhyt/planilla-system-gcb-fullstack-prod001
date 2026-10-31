/** Sprint 7: notificaciones RRHH, progreso de trabajos y versiones de export Planilla Core. */
import { useEffect, useState } from 'react'
import { Bell, BellRing, CheckCheck, Download } from 'lucide-react'
import { api, getToken } from './api'
import { Button, Card, Field, PageHeader, Pantalla, Pill, Toolbar } from './ui'
import { Chips, DataTable, type ColumnDef } from './ui/DataTable'
import { fallo, ok } from './ui/feedback'
import { conEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { fechaHora, useCarga } from './ui/hooks'
import { esperarTrabajo, ETIQUETA_ALERTA, textoTrabajo, Trabajo } from './trabajosLib'

export function ProgresoTrabajo({ t }: { t: Trabajo | null }) {
  if (!t) return null
  return <div data-testid="progreso-trabajo" className="flex items-center gap-3 rounded-card border border-border bg-surface px-4 py-3 text-sm shadow-card">
    <progress max={100} value={t.porcentaje} className="ds-progress h-2 w-60 overflow-hidden rounded-full" /> <span>{textoTrabajo(t)}</span></div>
}

/** Lanza un POST que puede devolver un trabajo y sigue su progreso. */
export function useTrabajo() {
  const [t, setT] = useState<Trabajo | null>(null)
  const seguir = (tr: Trabajo) => { setT(tr); return esperarTrabajo(tr.id, id => api<Trabajo>(`/trabajos/${id}`), x => setT({ ...x, modo: tr.modo })) }
  return { trabajo: t, seguir, limpiar: () => setT(null) }
}

export function useConteoNotificaciones(activo: boolean, refrescar = 0) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!activo) return
    const leer = () => api<{ no_leidas: number }>('/notificaciones/conteo').then(r => setN(r.no_leidas)).catch(() => {})
    leer(); const h = setInterval(leer, 60000); return () => clearInterval(h)
  }, [activo, refrescar])
  return n
}

const mesActual = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' }).slice(0, 7)

export function Notificaciones({ onCambio }: { onCambio?: () => void }) {
  const empresa = useEmpresaFiltro()
  const [periodo, setPeriodo] = useState(mesActual()); const [solo, setSolo] = useState<'no' | 'si'>('no')
  const [recarga, setRecarga] = useState(0); const c = { run: () => setRecarga(n => n + 1) }
  const generar = async () => {
    try { await api(`/notificaciones/generar?${conEmpresa({ periodo }, empresa)}`, { method: 'POST' }); ok(`Alertas de ${periodo} evaluadas.`); c.run(); onCambio?.() }
    catch (e) { fallo(e) }
  }
  const leer = async (n: any) => { await api(`/notificaciones/${n.id}/leida`, { method: 'POST' }).catch(() => {}); c.run(); onCambio?.() }
  const cols: ColumnDef<any, any>[] = [
    { accessorKey: 'tipo', header: 'Tipo', cell: x => <span className="flex items-center gap-2">{!x.row.original.leida && <span className="size-2 rounded-full bg-accent" aria-label="No leída" />}
      <Pill tono={/riesgo|perd/.test(x.getValue()) ? 'danger' : 'warning'}>{ETIQUETA_ALERTA[x.getValue()] || x.getValue()}</Pill></span> },
    { accessorKey: 'periodo', header: 'Periodo' },
    { accessorKey: 'mensaje', header: 'Mensaje', cell: x => <span className={x.row.original.leida ? '' : 'font-semibold'}>{x.getValue()}</span> },
    { accessorKey: 'creada_en', header: 'Creada', cell: x => fechaHora(x.getValue()) },
    { id: 'acc', header: '', enableSorting: false, cell: x => !x.row.original.leida && <Button size="sm" icon={CheckCheck} onClick={() => leer(x.row.original)}>Marcar leída</Button> },
  ]
  return <Pantalla>
    <PageHeader titulo="Notificaciones RRHH" icon={Bell} desc="Alertas internas: asistencia decidida que perdió sus marcas, pendientes cerca del cierre, riesgo part time y bonos sin aprobar. Se resuelven solas al corregirse la causa." />
    <Card><Toolbar>
      <Field label="Periodo"><input type="month" className="ds-input" value={periodo} onChange={e => setPeriodo(e.target.value)} /></Field>
      <Button variant="primary" icon={BellRing} onClick={generar}>Evaluar alertas</Button>
    </Toolbar></Card>
    <DataTable data={[]} columns={cols} servidor={{ url: '/notificaciones', params: { solo_no_leidas: solo === 'si', empresa_id: empresa }, clave: 'notif', recarga }} vacio="Sin alertas activas." filaClase={n => n.leida ? undefined : 'bg-accent-soft/40'}
      chips={<Chips label="Lectura" valor={solo} onChange={setSolo} chips={[{ valor: 'no', label: 'Todas' }, { valor: 'si', label: 'Solo no leídas' }]} />} />
  </Pantalla>
}

export async function descargarVersion(id: number) {
  const r = await fetch(`/api/reportes/export-planilla-core/versiones/${id}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!r.ok) throw new Error(String(r.status))
  const nombre = /filename=([^;]+)/.exec(r.headers.get('content-disposition') || '')?.[1] || 'export'
  const url = URL.createObjectURL(await r.blob()); const a = document.createElement('a'); a.href = url; a.download = nombre; a.click(); URL.revokeObjectURL(url)
}

export function VersionesExport({ empresa, periodo, recarga }: { empresa: string; periodo: string; recarga: number }) {
  const [vs, setVs] = useState<any[]>([])
  useEffect(() => {
    if (!empresa) { setVs([]); return }
    api<any[]>(`/reportes/export-planilla-core/versiones?empresa_id=${empresa}&periodo=${periodo}`).then(setVs).catch(() => setVs([]))
  }, [empresa, periodo, recarga])
  if (!empresa) return null
  const cols: ColumnDef<any, any>[] = [
    { accessorKey: 'version', header: 'Versión', cell: x => <b className="font-semibold">v{x.getValue()}</b> },
    { accessorKey: 'formato', header: 'Formato', cell: x => String(x.getValue()).toUpperCase() },
    { accessorKey: 'estado', header: 'Estado', cell: x => <Pill tono={x.getValue() === 'FINAL' ? 'success' : 'warning'}>{x.getValue()}</Pill> },
    { accessorKey: 'layout_version', header: 'Layout' }, { accessorKey: 'trabajadores', header: 'Trabajadores' }, { accessorKey: 'lineas', header: 'Líneas' },
    { accessorKey: 'checksum', header: 'Checksum', cell: x => <code title={x.getValue()} className="text-xs">{String(x.getValue()).slice(0, 12)}</code> },
    { accessorKey: 'generado_en', header: 'Generado', cell: x => fechaHora(x.getValue()) },
    { id: 'acc', header: '', enableSorting: false, cell: x => <Button size="sm" icon={Download} onClick={() => descargarVersion(x.row.original.id).catch(fallo)}>Descargar</Button> },
  ]
  return <div data-testid="versiones-export"><DataTable data={vs} columns={cols} buscar={false} vacio="Sin exportaciones registradas." titulo={`Versiones exportadas ${periodo}`} ordenInicial={[{ id: 'version', desc: true }]} /></div>
}
