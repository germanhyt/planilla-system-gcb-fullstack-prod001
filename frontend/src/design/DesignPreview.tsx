// Ruta SOLO DEV: /design-preview — tokens + componentes en ambos temas.
import { useMemo, useState } from 'react'
import { Banknote, Bell, CalendarDays, ChevronLeft, ChevronRight, Clock, Download, Filter, LayoutDashboard, Plus, Search, Settings, Users, Wallet } from 'lucide-react'
import { createColumnHelper, flexRender, getCoreRowModel, getFilteredRowModel, getPaginationRowModel, useReactTable } from '@tanstack/react-table'
import { ArcElement, CategoryScale, Chart as ChartJS, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip } from 'chart.js'
import { Doughnut, Line } from 'react-chartjs-2'
import { Button, Card, KpiCard, Segmented, SidebarItem, StatusPill, ThemeToggle, cn, type Status } from '../ui'
import { tokens, type Theme } from '../theme/tokens'

ChartJS.register(ArcElement, CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

type Row = { nombre: string; area: string; bruto: number; desc: number; estado: Status }
const AREAS = ['Operaciones', 'Administración', 'Ventas', 'TI']
const NOMBRES = ['Ana Quispe', 'Luis Rojas', 'María Torres', 'Jorge Huamán', 'Rosa Flores', 'Carlos Vega', 'Lucía Paredes', 'Pedro Castillo', 'Elena Díaz', 'Miguel Soto', 'Sofía Ramos', 'Diego Chávez']
const DATA: Row[] = NOMBRES.map((n, i) => ({ nombre: n, area: AREAS[i % 4], bruto: 2500 + i * 310, desc: 280 + i * 37, estado: (['pagado', 'pendiente', 'pagado', 'rechazado'] as Status[])[i % 4] }))
const pen = (n: number) => 'S/ ' + n.toLocaleString('es-PE', { minimumFractionDigits: 2 })
const ch = createColumnHelper<Row>()
const COLS = [
  ch.accessor('nombre', { header: 'Colaborador' }),
  ch.accessor('area', { header: 'Área' }),
  ch.accessor('bruto', { header: 'Bruto', cell: c => pen(c.getValue()) }),
  ch.accessor('desc', { header: 'Descuentos', cell: c => <span className="text-danger">-{pen(c.getValue())}</span> }),
  ch.display({ id: 'neto', header: 'Neto', cell: c => <span className="font-semibold text-success">{pen(c.row.original.bruto - c.row.original.desc)}</span> }),
  ch.accessor('estado', { header: 'Estado', cell: c => <StatusPill status={c.getValue()} />, filterFn: 'equalsString' }),
]

function Table() {
  const [q, setQ] = useState(''); const [chip, setChip] = useState<Status | 'todos'>('todos')
  const t = useReactTable({ data: DATA, columns: COLS, state: { globalFilter: q, columnFilters: chip === 'todos' ? [] : [{ id: 'estado', value: chip }] },
    onGlobalFilterChange: setQ, getCoreRowModel: getCoreRowModel(), getFilteredRowModel: getFilteredRowModel(), getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 5 } } })
  return <Card className="p-0">
    <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
      <label className="flex items-center gap-2 rounded-ctl border border-line bg-surface-2 px-3 py-1.5 text-sm text-muted">
        <Search size={14} aria-hidden /><input aria-label="Buscar" placeholder="Buscar colaborador" value={q} onChange={e => setQ(e.target.value)} className="border-0 bg-transparent text-fg outline-none" />
      </label>
      {(['todos', 'pagado', 'pendiente', 'rechazado'] as const).map(c => <button key={c} onClick={() => setChip(c)} aria-pressed={chip === c}
        className={cn('rounded-full border px-3 py-1 text-xs capitalize cursor-pointer', chip === c ? 'border-primary bg-primary text-primary-fg' : 'border-line bg-surface text-muted')}>{c}</button>)}
    </div>
    <table className="w-full border-collapse text-sm">
      <thead>{t.getHeaderGroups().map(g => <tr key={g.id}>{g.headers.map(h => <th key={h.id} className="border-b border-line bg-surface-2 px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-muted">{flexRender(h.column.columnDef.header, h.getContext())}</th>)}</tr>)}</thead>
      <tbody>{t.getRowModel().rows.map(r => <tr key={r.id} className="hover:bg-surface-2">{r.getVisibleCells().map(c => <td key={c.id} className="border-b border-line px-3 py-2.5">{flexRender(c.column.columnDef.cell, c.getContext())}</td>)}</tr>)}</tbody>
    </table>
    <div className="flex items-center justify-between p-3 text-sm text-muted">
      <span>Página {t.getState().pagination.pageIndex + 1} de {Math.max(1, t.getPageCount())} · {t.getFilteredRowModel().rows.length} registros</span>
      <div className="flex gap-2"><Button aria-label="Anterior" icon={ChevronLeft} disabled={!t.getCanPreviousPage()} onClick={() => t.previousPage()} /><Button aria-label="Siguiente" icon={ChevronRight} disabled={!t.getCanNextPage()} onClick={() => t.nextPage()} /></div>
    </div>
  </Card>
}

function Charts({ theme }: { theme: Theme }) {
  const k = tokens[theme]
  const grid = { color: k.border }, ticks = { color: k.muted }
  return <div className="grid gap-4 md:grid-cols-3">
    <Card className="md:col-span-2"><h3 className="m-0 mb-2 text-sm font-semibold">Costo de planilla</h3>
      <div className="h-56"><Line options={{ maintainAspectRatio: false, plugins: { legend: { labels: { color: k.muted } } }, scales: { x: { grid, ticks }, y: { grid, ticks } } }}
        data={{ labels: ['May', 'Jun', 'Jul', 'Ago', 'Set', 'Oct'], datasets: [
          { label: 'Neto', data: [182, 190, 188, 201, 210, 219], borderColor: k.blue, backgroundColor: k.blue + '33', fill: true, tension: 0.35 },
          { label: 'Horas extra', data: [22, 25, 19, 28, 26, 31], borderColor: k.amber, tension: 0.35 }] }} /></div></Card>
    <Card><h3 className="m-0 mb-2 text-sm font-semibold">Estado de pagos</h3>
      <div className="h-56"><Doughnut options={{ maintainAspectRatio: false, cutout: '70%', plugins: { legend: { position: 'bottom', labels: { color: k.muted } } } }}
        data={{ labels: ['Pagado', 'Pendiente', 'Rechazado'], datasets: [{ data: [68, 24, 8], backgroundColor: [k.teal, k.amber, k.danger], borderColor: k.surface }] }} /></div></Card>
  </div>
}

function Board({ theme }: { theme: Theme }) {
  const [period, setPeriod] = useState<'Semanal' | 'Mensual' | 'Anual'>('Mensual')
  const [act, setAct] = useState('Planillas')
  const nav = useMemo(() => [
    { g: 'General', items: [{ i: LayoutDashboard, l: 'Dashboard' }, { i: Users, l: 'Colaboradores', c: 124 }] },
    { g: 'Nómina', items: [{ i: Wallet, l: 'Planillas', c: 3 }, { i: Clock, l: 'Asistencia' }, { i: Bell, l: 'Notificaciones', c: 7 }] },
    { g: 'Sistema', items: [{ i: Settings, l: 'Configuración' }] }], [])
  return <div data-theme={theme} className="ds rounded-card border border-line p-0 overflow-hidden">
    <div className="flex min-h-[640px]">
      <aside className="w-60 shrink-0 border-r border-line bg-surface-2 p-3">
        <div className="mb-4 flex items-center gap-2 px-2"><img src={`/brand/logo-mark-${theme === 'dark' ? 'dark' : 'light'}-bg.png`} alt="GCB" className="h-6" /><span className="text-sm font-semibold">Planillas</span></div>
        {nav.map(s => <div key={s.g} className="mb-3"><div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">{s.g}</div>
          {s.items.map(it => <SidebarItem key={it.l} icon={it.i} label={it.l} count={(it as { c?: number }).c} active={act === it.l} onClick={() => setAct(it.l)} />)}</div>)}
      </aside>
      <main className="flex-1 space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <nav aria-label="breadcrumb" className="text-sm text-muted">Nómina / <span className="text-fg font-semibold">{act}</span></nav>
          <div className="flex gap-2"><Button icon={Filter}>Filtrar</Button><Button icon={Download}>Exportar</Button><Button variant="primary" icon={Plus}>Nueva planilla</Button><ThemeToggle /></div>
        </div>
        <Segmented label="Periodo" options={['Semanal', 'Mensual', 'Anual']} value={period} onChange={setPeriod} />
        <div className="grid gap-4 md:grid-cols-4">
          <KpiCard icon={Users} label="Colaboradores" value="124" delta={3.2} />
          <KpiCard icon={Banknote} label="Neto pagado" value="S/ 219k" delta={4.3} accent="teal" />
          <KpiCard icon={Clock} label="Horas extra" value="312 h" delta={-6.1} accent="amber" />
          <KpiCard icon={CalendarDays} label="Ausencias" value="18" delta={-2.0} />
        </div>
        <Charts theme={theme} />
        <Table />
        <div className="flex flex-wrap gap-2"><Button variant="primary">Primario</Button><Button>Secundario</Button><Button variant="ghost">Ghost</Button><Button variant="danger">Peligro</Button><Button disabled>Deshabilitado</Button>
          <StatusPill status="pagado" /><StatusPill status="pendiente" /><StatusPill status="rechazado" /></div>
      </main>
    </div>
  </div>
}

function Swatches({ theme }: { theme: Theme }) {
  return <div data-theme={theme} className="ds grid grid-cols-3 gap-2 rounded-card border border-line p-3 md:grid-cols-6">
    {Object.entries(tokens[theme]).map(([k, v]) => <div key={k} className="text-xs"><div className="h-10 rounded-ctl border border-line" style={{ background: v }} /><div className="mt-1 font-mono">{k}</div><div className="text-muted font-mono">{v}</div></div>)}
  </div>
}

export default function DesignPreview() {
  return <div className="ds min-h-screen space-y-6 p-6">
    <header className="flex items-center justify-between"><h1 className="m-0 text-xl font-semibold">Design system · preview (dev)</h1><ThemeToggle /></header>
    {(['dark', 'light'] as const).map(t => <section key={t} className="space-y-3"><h2 className="m-0 text-base font-semibold">Tema {t}{t === 'dark' ? ' (por defecto)' : ''}</h2><Swatches theme={t} /><Board theme={t} /></section>)}
  </div>
}
