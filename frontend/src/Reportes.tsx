/** Sprint 3 / Incremento 3: Reportes mensuales (RRHH/admin todo, jefe sólo su unidad) y exportación a Planilla Core. */
import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Clock, Download, FileUp, Layers, Moon, RefreshCw, Timer, Users } from 'lucide-react'
import { api, getToken } from './api'
import { Aviso, Button, Card, Field, KpiCard, PageHeader, Pantalla, Pill, Toolbar } from './ui'
import { DataTable, type ColumnDef } from './ui/DataTable'
import { confirmar, fallo, ok } from './ui/feedback'
import { guardarEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { ProgresoTrabajo, useTrabajo, VersionesExport } from './Trabajos'

const mesActual = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' }).slice(0, 7)
const n = (v: number | null | undefined) => (v === null || v === undefined ? '—' : Number(v).toFixed(2))

interface Fila {
  trabajador_id: number; codigo: string; trabajador: string; empresa: string; horas_trabajadas: number; horas_normales: number
  tardanza_min: number; horas_extra_25: number; horas_extra_35: number; horas_nocturnas: number; recargo_nocturno_horas: number | null
  bono_3am: number; bono_3am_monto: number; banco_horas_mes: number; banco_horas_saldo: number; ausencias: number
}
interface Resp { periodo: string; desde: string; hasta: string; periodo_cerrado?: boolean; muestra_recargo_nocturno?: boolean; registros: Fila[]; totales: Record<string, number> }

async function descargar(path: string, method = 'GET'): Promise<{ nombre: string; estado: string | null; reutilizada: boolean }> {
  const r = await fetch('/api' + path, { method, headers: { Authorization: `Bearer ${getToken()}` } })
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(typeof d.detail === 'string' ? d.detail : String(r.status)) }
  const nombre = /filename=([^;]+)/.exec(r.headers.get('content-disposition') || '')?.[1] || 'reporte'
  const url = URL.createObjectURL(await r.blob()); const a = document.createElement('a'); a.href = url; a.download = nombre; a.click(); URL.revokeObjectURL(url)
  return { nombre, estado: r.headers.get('x-export-estado'), reutilizada: r.headers.get('x-export-reutilizada') === '1' }
}

export function Reportes({ rol }: { rol: string }) {
  const gestor = rol === 'rrhh' || rol === 'admin'
  const global = useEmpresaFiltro()
  const [empresas, setEmpresas] = useState<any[]>([]); const [periodo, setPeriodo] = useState(mesActual())
  const [primera, setPrimera] = useState('')
  const empresa = gestor ? global : (global || primera)
  const { trabajo, seguir, limpiar } = useTrabajo(); const [recarga, setRecarga] = useState(0)
  const [data, setData] = useState<Resp | null>(null); const [err, setErr] = useState(''); const [cargando, setCargando] = useState(false); const [fmtPc, setFmtPc] = useState<'csv' | 'json'>('csv')
  useEffect(() => { api<any[]>('/empresas').then(e => { setEmpresas(e); if (e.length) setPrimera(String(e[0].id)) }).catch(() => {}) }, [])
  const q = () => { const p = new URLSearchParams({ periodo }); if (empresa) p.set('empresa_id', empresa); return p }
  const cargar = () => { setErr(''); setCargando(true); api<Resp>(`/reportes/consolidado-mensual?${q()}`).then(setData).catch(e => setErr(e.message)).finally(() => setCargando(false)) }
  useEffect(() => { if (periodo) cargar() }, [empresa, periodo])
  const recargo = !!(data?.muestra_recargo_nocturno ?? data?.registros.some(r => r.recargo_nocturno_horas !== null))
  const bajar = (formato: string) => descargar(`/reportes/consolidado-mensual?${q()}&formato=${formato}`).then(r => ok(`Descargado ${r.nombre}.`)).catch(fallo)
  const exportar = async () => {
    if (!empresa) { fallo('Seleccione una empresa'); return }
    if (data && !data.periodo_cerrado && !await confirmar({ titulo: 'Periodo abierto', mensaje: 'El periodo no está cerrado: el archivo se generará marcado PRELIMINAR. ¿Continuar?', ok: 'Exportar' })) return
    try { const r = await descargar(`/reportes/export-planilla-core?${q()}&formato=${fmtPc}`, 'POST'); setRecarga(x => x + 1); ok(r.reutilizada ? `Sin cambios: se reutiliza ${r.nombre} (checksum igual).` : `Generado ${r.nombre} (${r.estado}). Registrado en auditoría.`) } catch (e) { fallo(e) }
  }
  const exportarLote = async () => {
    limpiar()
    try {
      const p = new URLSearchParams({ periodo, formato: fmtPc }); if (empresa) p.set('empresa_id', empresa)
      const tr = await api(`/reportes/export-planilla-core/lote?${p}`, { method: 'POST' })
      const fin = await seguir(tr); setRecarga(x => x + 1)
      if (fin.estado === 'ok') ok(`Lote exportado (${fin.total} empresa(s)). Ver versiones abajo.`); else fallo(fin.error || 'Error en lote')
    } catch (e) { fallo(e) }
  }
  const t = data?.totales
  const num = (k: keyof Fila, h: string) => ({ accessorKey: k, header: h, cell: (x: any) => <span className="tabular-nums">{n(x.getValue())}</span> }) as ColumnDef<Fila, any>
  const cols = useMemo<ColumnDef<Fila, any>[]>(() => [
    { accessorKey: 'codigo', header: 'Código' }, { accessorKey: 'trabajador', header: 'Trabajador', cell: x => <b className="font-semibold">{x.getValue()}</b> },
    { accessorKey: 'empresa', header: 'Empresa', cell: x => <Pill tono="accent">{x.getValue()}</Pill> },
    num('horas_trabajadas', 'H. trabajadas'), num('horas_normales', 'H. normales'),
    { accessorKey: 'tardanza_min', header: 'Tardanza (min)', cell: x => x.getValue() ? <Pill tono="warning">{x.getValue()}</Pill> : '0' },
    num('horas_extra_25', 'HE 25%'), num('horas_extra_35', 'HE 35%'), num('horas_nocturnas', 'H. nocturnas 22-06'),
    ...(recargo ? [num('recargo_nocturno_horas', 'Recargo nocturno (h)')] : []),
    { accessorKey: 'bono_3am', header: 'Bono 3 AM' },
    { accessorKey: 'bono_3am_monto', header: 'Bono 3 AM (S/)', cell: x => x.getValue() ? x.getValue().toFixed(2) : '' },
    num('banco_horas_mes', 'Banco h. (mes)'), num('banco_horas_saldo', 'Banco h. (saldo)'),
    { accessorKey: 'ausencias', header: 'Ausencias', cell: x => x.getValue() ? <Pill tono="danger">{x.getValue()}</Pill> : '0' },
  ], [recargo])
  return <Pantalla>
    <PageHeader titulo={`Reportes ${rol === 'jefe' ? 'de mi unidad' : ''}`.trim()} icon={BarChart3}
      desc="Mes calendario; cada turno cuenta en el mes de su día operativo. Horas nocturnas 22:00–06:00 siempre calculadas; el recargo nocturno se muestra aparte sólo en empresas que lo pagan por separado. Bono 3 AM: cantidad aprobada (monto lo fija administración).">
      {data && empresa && <Pill tono={data.periodo_cerrado ? 'success' : 'warning'}>{data.periodo_cerrado ? 'CERRADO (export FINAL)' : 'ABIERTO (export PRELIMINAR)'}</Pill>}
    </PageHeader>
    <Card><Toolbar>
      <Field label="Empresa"><select className="ds-input" value={global} onChange={e => guardarEmpresa(e.target.value)}>
        {gestor ? <option value="">Todas</option> : <option value="">{empresas[0]?.codigo ?? '—'}</option>}{empresas.map(e => <option key={e.id} value={e.id}>{e.codigo}</option>)}</select></Field>
      <Field label="Periodo"><input type="month" className="ds-input" value={periodo} onChange={e => setPeriodo(e.target.value)} /></Field>
      <Button icon={RefreshCw} onClick={cargar}>Actualizar</Button>
      <Button icon={Download} onClick={() => bajar('csv')}>CSV</Button>
      <Button icon={Download} onClick={() => bajar('xlsx')}>XLSX</Button>
      {gestor && <><Field label="Formato interfaz"><select className="ds-input" value={fmtPc} onChange={e => setFmtPc(e.target.value as 'csv' | 'json')} title="Formato interfaz"><option value="csv">CSV</option><option value="json">JSON</option></select></Field>
        <Button variant="primary" icon={FileUp} onClick={exportar} disabled={!empresa}>Exportar a Planilla Core</Button>
        <Button icon={Layers} onClick={exportarLote}>Exportar lote (segundo plano)</Button></>}
    </Toolbar></Card>
    {data && empresa && <span className="sr-only">Periodo {data.desde} a {data.hasta}</span>}
    <ProgresoTrabajo t={trabajo} />
    {t && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard icon={Clock} label="Horas trabajadas" value={n(t.total_horas_trabajadas)} sub={`${t.total_trabajadores} trabajadores`} />
      <KpiCard icon={Timer} label="Horas extra (25 % + 35 %)" value={n((t.total_horas_extra_25 || 0) + (t.total_horas_extra_35 || 0))} accent="amber" sub={`${n(t.total_horas_extra_25)} + ${n(t.total_horas_extra_35)}`} />
      <KpiCard icon={Moon} label="Horas nocturnas" value={n(t.total_horas_nocturnas)} accent="teal" sub={`Bono 3 AM: ${t.total_bono_3am ?? 0}`} />
      <KpiCard icon={Users} label="Tardanza total" value={`${t.total_tardanza_min ?? 0} min`} accent="danger" sub={`${data?.desde} → ${data?.hasta}`} />
    </div>}
    {err && <Aviso tono="danger">{err}</Aviso>}
    <DataTable data={data?.registros ?? []} columns={cols} cargando={cargando && !data} vacio="Sin asistencia registrada en el periodo." tam={25} buscar="Buscar trabajador o código" titulo="Consolidado mensual" />
    {gestor && <VersionesExport empresa={empresa || primera} periodo={periodo} recarga={recarga} />}
  </Pantalla>
}
