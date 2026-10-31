import { useEffect, useMemo, useState } from 'react'
import { ArcElement, CategoryScale, Chart as ChartJS, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip } from 'chart.js'
import { Doughnut, Line } from 'react-chartjs-2'
import { AlarmClock, Bell, Clock, LayoutDashboard, Timer, UserX } from 'lucide-react'
import { api } from './api'
import { Card, ErrorBox, KpiCard, PageHeader, Pantalla, Pill, PillEstado, Segmented, Cargando } from './ui'
import { DataTable, type ColumnDef } from './ui/DataTable'
import { conEmpresa, useEmpresaFiltro } from './ui/empresaFiltro'
import { mesLima } from './ui/hooks'
import { TIPOS, type Item } from './Excepciones'

ChartJS.register(ArcElement, CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

type Periodo = 'mes' | 'anterior' | 'trimestre'
const ETQ: Record<Periodo, string> = { mes: 'Este mes', anterior: 'Mes anterior', trimestre: 'Trimestre' }
const mesMenos = (p: string, n: number) => { const [y, m] = p.split('-').map(Number); const d = new Date(y, m - 1 - n, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` }
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const etiquetaMes = (p: string) => `${MESES[Number(p.slice(5)) - 1]} ${p.slice(2, 4)}`
interface Resumen { trabajadas: number; normales: number; he25: number; he35: number; nocturnas: number; tardanzaH: number; ausencias: number; trabajadores: number }
const cero: Resumen = { trabajadas: 0, normales: 0, he25: 0, he35: 0, nocturnas: 0, tardanzaH: 0, ausencias: 0, trabajadores: 0 }
const resumir = (r: any): Resumen => { const t = r?.totales ?? {}
  return { trabajadas: +t.total_horas_trabajadas || 0, normales: +t.total_horas_normales || 0, he25: +t.total_horas_extra_25 || 0, he35: +t.total_horas_extra_35 || 0,
    nocturnas: +t.total_horas_nocturnas || 0, tardanzaH: (+t.total_tardanza_min || 0) / 60, trabajadores: +t.total_trabajadores || 0,
    ausencias: (r?.registros ?? []).reduce((a: number, x: any) => a + (+x.ausencias || 0), 0) } }
const sumar = (xs: Resumen[]) => xs.reduce((a, b) => ({ trabajadas: a.trabajadas + b.trabajadas, normales: a.normales + b.normales, he25: a.he25 + b.he25, he35: a.he35 + b.he35,
  nocturnas: a.nocturnas + b.nocturnas, tardanzaH: a.tardanzaH + b.tardanzaH, ausencias: a.ausencias + b.ausencias, trabajadores: Math.max(a.trabajadores, b.trabajadores) }), cero)
const delta = (a: number, b: number) => b ? ((a - b) / b) * 100 : null
const fmt = (v: number) => v.toLocaleString('es-PE', { maximumFractionDigits: 1 })

/** Lee un token CSS actual (cambia con el tema). */
function useTokens() {
  const leer = () => { const s = getComputedStyle(document.documentElement); const g = (k: string) => s.getPropertyValue(k).trim() || '#888'
    return { accent: g('--c-accent'), strong: g('--c-accent-strong'), amber: g('--c-amber'), teal: g('--c-teal'), danger: g('--c-danger'), muted: g('--c-muted'), border: g('--c-border'), text: g('--c-text'), surface: g('--c-surface') } }
  const [t, setT] = useState(leer)
  useEffect(() => { const o = new MutationObserver(() => setT(leer())); o.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'style'] }); return () => o.disconnect() }, [])
  return t
}

export function Dashboard({ rol }: { rol: string }) {
  const empresa = useEmpresaFiltro(); const k = useTokens()
  const [per, setPer] = useState<Periodo>('mes')
  const [meses, setMeses] = useState<Record<string, Resumen> | null>(null); const [err, setErr] = useState('')
  const [pend, setPend] = useState<Item[] | null>(null); const [alertas, setAlertas] = useState<any[]>([])
  const actual = mesLima(); const lista = useMemo(() => Array.from({ length: 9 }, (_, i) => mesMenos(actual, 8 - i)), [actual])
  const cargar = () => {
    setErr(''); setMeses(null)
    Promise.all(lista.map(p => api(`/reportes/consolidado-mensual?${conEmpresa({ periodo: p }, empresa)}`).then(resumir).catch(e => { if (p === actual) throw e; return cero })))
      .then(rs => setMeses(Object.fromEntries(lista.map((p, i) => [p, rs[i]])))).catch(e => setErr(e.message))
    const hace = new Date(Date.now() - 30 * 86400000).toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
    api<Item[]>(`/excepciones/bandeja?${conEmpresa({ desde: hace, hasta: new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' }), estado: 'pendiente' }, empresa)}`).then(setPend).catch(() => setPend([]))
    if (rol !== 'jefe') api<any[]>(`/notificaciones?${conEmpresa({ solo_no_leidas: true }, empresa)}`).then(a => setAlertas(a.slice(0, 5))).catch(() => setAlertas([]))
  }
  useEffect(cargar, [empresa])
  const ventana = (p: Periodo, desplaz = 0): string[] => { const n = p === 'trimestre' ? 3 : 1; const fin = (p === 'anterior' ? 1 : 0) + desplaz * n
    return Array.from({ length: n }, (_, i) => mesMenos(actual, fin + i)) }
  const cur = meses ? sumar(ventana(per).map(p => meses[p] ?? cero)) : null
  const prev = meses ? sumar(ventana(per, 1).map(p => meses[p] ?? cero)) : null
  const tendencia = lista.slice(-6)
  const cols = useMemo<ColumnDef<Item, any>[]>(() => [
    { accessorKey: 'dia', header: 'Día' },
    { id: 't', accessorFn: i => i.trabajador.nombre, header: 'Trabajador', cell: x => <span className="flex items-center gap-2"><span className="grid size-8 place-items-center rounded-full bg-accent-soft text-xs font-bold text-accent">{x.getValue().split(' ').map((w: string) => w[0]).slice(0, 2).join('')}</span>
      <span><b className="font-semibold">{x.getValue()}</b><span className="block text-xs text-muted">{x.row.original.trabajador.codigo}</span></span></span> },
    { accessorKey: 'tipo', header: 'Tipo', cell: x => TIPOS[x.getValue()] ?? x.getValue() },
    { accessorKey: 'detalle', header: 'Detalle' },
    { accessorKey: 'estado', header: 'Estado', cell: x => <PillEstado estado={x.getValue()} /> },
  ], [])
  return <Pantalla>
    <PageHeader titulo="Dashboard" icon={LayoutDashboard} desc={`Resumen de asistencia ${rol === 'jefe' ? 'de su unidad' : 'de la empresa seleccionada'} con datos consolidados reales.`}>
      <Segmented label="Periodo del resumen" options={['mes', 'anterior', 'trimestre'] as const} value={per} onChange={setPer} labels={ETQ} />
    </PageHeader>
    {err && <ErrorBox msg={err} reintentar={cargar} />}
    {!err && !cur && <Cargando texto="Calculando indicadores…" />}
    {cur && prev && <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard icon={Clock} label="Horas trabajadas" value={fmt(cur.trabajadas)} delta={delta(cur.trabajadas, prev.trabajadas)} sub={`${cur.trabajadores} trabajadores · vs. periodo anterior`} />
        <KpiCard icon={Timer} label="Horas extra" value={fmt(cur.he25 + cur.he35)} delta={delta(cur.he25 + cur.he35, prev.he25 + prev.he35)} accent="amber" invertir />
        <KpiCard icon={AlarmClock} label="Tardanzas (h)" value={fmt(cur.tardanzaH)} delta={delta(cur.tardanzaH, prev.tardanzaH)} accent="danger" invertir />
        <KpiCard icon={UserX} label="Ausencias" value={fmt(cur.ausencias)} delta={delta(cur.ausencias, prev.ausencias)} accent="teal" invertir />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2"><div className="mb-3 flex items-center justify-between"><p className="m-0 font-semibold">Tendencia de horas</p><span className="text-xs text-muted">últimos 6 meses</span></div>
          <div className="h-72"><Line options={{ maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { labels: { color: k.muted, usePointStyle: true } } },
            scales: { x: { ticks: { color: k.muted }, grid: { display: false } }, y: { ticks: { color: k.muted }, grid: { color: k.border } } } }}
            data={{ labels: tendencia.map(etiquetaMes), datasets: [
              { label: 'Trabajadas', data: tendencia.map(p => meses![p]?.trabajadas ?? 0), borderColor: k.accent, backgroundColor: k.accent + '33', fill: true, tension: .4, pointRadius: 3 },
              { label: 'Horas extra', data: tendencia.map(p => (meses![p]?.he25 ?? 0) + (meses![p]?.he35 ?? 0)), borderColor: k.amber, backgroundColor: k.amber + '22', fill: true, tension: .4, pointRadius: 3 }] }} /></div></Card>
        <Card><p className="m-0 mb-3 font-semibold">Distribución de horas</p>
          {cur.normales + cur.he25 + cur.he35 + cur.nocturnas + cur.tardanzaH > 0 ? <div className="h-64"><Doughnut options={{ maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom', labels: { color: k.muted, usePointStyle: true, boxWidth: 8 } } } }}
            data={{ labels: ['Normales', 'HE 25 %', 'HE 35 %', 'Nocturnas', 'Tardanzas'], datasets: [{ data: [cur.normales, cur.he25, cur.he35, cur.nocturnas, cur.tardanzaH].map(v => +v.toFixed(2)),
              backgroundColor: [k.accent, k.amber, k.strong + '99', k.teal, k.danger], borderColor: k.surface, borderWidth: 2 }] }} /></div>
            : <p className="text-sm text-muted">Sin horas registradas en {ETQ[per].toLowerCase()}.</p>}</Card>
      </div>
    </>}
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="xl:col-span-2"><DataTable data={pend ?? []} columns={cols} cargando={!pend} buscar={false} tam={6} titulo="Excepciones recientes por decidir" vacio="Sin excepciones pendientes en los últimos 30 días." /></div>
      <Card><p className="m-0 mb-3 flex items-center gap-2 font-semibold"><Bell size={16} className="text-accent" />Alertas</p>
        {rol === 'jefe' ? <p className="text-sm text-muted">{pend?.length ?? 0} excepciones pendientes en su unidad.</p>
          : alertas.length ? <ul className="m-0 grid list-none gap-2 p-0">{alertas.map(a => <li key={a.id} className="rounded-ctl border border-border p-2.5 text-sm">
            <Pill tono="warning">{a.periodo}</Pill> <span className="mt-1 block">{a.mensaje}</span></li>)}</ul>
          : <p className="text-sm text-muted">Sin alertas no leídas.</p>}</Card>
    </div>
  </Pantalla>
}
