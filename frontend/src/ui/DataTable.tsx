// Tabla de datos (TanStack): búsqueda, chips de filtro, columnas ordenables, paginación numerada y estados vacío/carga/error.
// Modo `servidor`: paginación/orden/búsqueda en el backend (?page&page_size&sort&q -> {items,total,page,page_size}),
// búsqueda con debounce y estado sincronizado con la URL (?<clave>.page, .size, .sort, .q).
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from '../api'
import { type ColumnDef, flexRender, getCoreRowModel, getFilteredRowModel, getPaginationRowModel, getSortedRowModel,
  type SortingState, useReactTable } from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Search } from 'lucide-react'
import { Cargando, cn, ErrorBox, Vacio } from '.'

export type { ColumnDef }
export type Chip<V extends string = string> = { valor: V; label: string; n?: number }

export function Chips<V extends string>({ chips, valor, onChange, label = 'Filtro' }: { chips: Chip<V>[]; valor: V; onChange: (v: V) => void; label?: string }) {
  return <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
    {chips.map(c => <button type="button" key={c.valor} aria-pressed={c.valor === valor} onClick={() => onChange(c.valor)}
      className={cn('rounded-full border px-3 py-1 text-xs font-medium cursor-pointer transition',
        c.valor === valor ? 'border-primary bg-primary text-primary-fg' : 'border-line bg-surface text-muted hover:text-fg')}>
      {c.label}{c.n != null && <span className="ml-1.5 opacity-75">{c.n}</span>}</button>)}
  </div>
}

type Props<T> = {
  data: T[]; columns: ColumnDef<T, any>[]; buscar?: string | false; chips?: ReactNode; acciones?: ReactNode; titulo?: ReactNode
  cargando?: boolean; error?: string; reintentar?: () => void; vacio?: string; tam?: number; ordenInicial?: SortingState
  filaClase?: (f: T) => string | undefined; testid?: string; compacta?: boolean
  /** Paginación server-side: `url` del listado y filtros extra (vacíos se omiten); `clave` prefija el estado en la URL; cambiar `recarga` vuelve a pedir. */
  servidor?: { url: string; params?: Record<string, string | number | boolean | null | undefined>; clave?: string; recarga?: number }
  tamanos?: number[]
}
export type Pagina<T> = { items: T[]; total: number; page: number; page_size: number }

const leerURL = (k: string) => new URLSearchParams(location.search).get(k)
function escribirURL(vals: Record<string, string | number | null>) {
  const u = new URL(location.href)
  for (const [k, v] of Object.entries(vals)) v === null || v === '' ? u.searchParams.delete(k) : u.searchParams.set(k, String(v))
  if (u.href !== location.href) history.replaceState(history.state, '', u)
}
/** Valor con debounce (ms). */
export function useDebounce<V>(v: V, ms = 350): V {
  const [d, setD] = useState(v)
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t) }, [v, ms])
  return d
}
/** Números de página con elipsis: 1 … 4 5 6 … 20 */
export function paginas(actual: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const s = new Set([1, total, actual - 1, actual, actual + 1].filter(n => n >= 1 && n <= total))
  const xs = [...s].sort((a, b) => a - b); const out: (number | '…')[] = []
  xs.forEach((n, i) => { if (i && n - xs[i - 1] > 1) out.push('…'); out.push(n) })
  return out
}
export function rango(page: number, size: number, total: number) {
  return total === 0 ? 'Sin resultados' : `Mostrando ${(page - 1) * size + 1} a ${Math.min(total, page * size)} de ${total}`
}

export function DataTable<T>({ data, columns, buscar = 'Buscar…', chips, acciones, titulo, cargando, error, reintentar, vacio, tam = 10,
  ordenInicial = [], filaClase, testid, compacta, servidor, tamanos = [10, 20, 50, 100] }: Props<T>) {
  const k = servidor?.clave ?? testid ?? 't'
  const enUrl = !!servidor
  const [sorting, setSorting] = useState<SortingState>(() => {
    const v = enUrl && leerURL(`${k}.sort`); return v ? [{ id: v.replace(/^-/, ''), desc: v.startsWith('-') }] : ordenInicial })
  const [q, setQ] = useState(() => (enUrl && leerURL(`${k}.q`)) || '')
  const [pag, setPag] = useState(() => ({ pageIndex: Math.max(0, Number(enUrl && leerURL(`${k}.page`) || 1) - 1), pageSize: Number(enUrl && leerURL(`${k}.size`)) || tam }))
  const qd = useDebounce(q)
  const [res, setRes] = useState<Pagina<T> | null>(null); const [sErr, setSErr] = useState(''); const [sCarga, setSCarga] = useState(false)
  const pid = useRef(0)
  const filtros = JSON.stringify(servidor?.params ?? {})
  const sort = sorting[0] ? `${sorting[0].desc ? '-' : ''}${sorting[0].id}` : ''
  const pedir = () => {
    if (!servidor) return
    const p = new URLSearchParams()
    Object.entries(servidor.params ?? {}).forEach(([a, b]) => { if (b !== '' && b != null) p.set(a, String(b)) })
    p.set('page', String(pag.pageIndex + 1)); p.set('page_size', String(pag.pageSize)); if (sort) p.set('sort', sort); if (qd) p.set('q', qd)
    const id = ++pid.current; setSCarga(true); setSErr('')
    api<Pagina<T>>(`${servidor.url}${servidor.url.includes('?') ? '&' : '?'}${p}`)
      .then(r => { if (id !== pid.current) return; setRes(r); if (r.page - 1 !== pag.pageIndex) setPag(x => ({ ...x, pageIndex: r.page - 1 })) })
      .catch(e => id === pid.current && setSErr(e.message)).finally(() => id === pid.current && setSCarga(false))
  }
  // filtros/búsqueda nuevos -> página 1
  const prim = useRef(true)
  useEffect(() => { if (prim.current) { prim.current = false; return } setPag(x => ({ ...x, pageIndex: 0 })) }, [filtros, qd])
  useEffect(pedir, [servidor?.url, filtros, qd, sort, pag.pageIndex, pag.pageSize, servidor?.recarga])
  useEffect(() => { if (enUrl) escribirURL({ [`${k}.page`]: pag.pageIndex ? pag.pageIndex + 1 : null, [`${k}.size`]: pag.pageSize !== tam ? pag.pageSize : null, [`${k}.sort`]: sort || null, [`${k}.q`]: qd || null }) },
    [pag, sort, qd])
  const filas = servidor ? res?.items ?? [] : data
  const cols = useMemo(() => columns, [columns])
  const t = useReactTable({ data: filas, columns: cols, state: { sorting, globalFilter: servidor ? undefined : q, pagination: pag },
    onSortingChange: u => { setSorting(u); if (servidor) setPag(x => ({ ...x, pageIndex: 0 })) }, onGlobalFilterChange: setQ, onPaginationChange: setPag,
    manualPagination: !!servidor, manualSorting: !!servidor, manualFiltering: !!servidor, rowCount: servidor ? res?.total ?? 0 : undefined,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(), autoResetPageIndex: !servidor,
    globalFilterFn: (row, _c, v) => JSON.stringify(row.original).toLowerCase().includes(String(v).toLowerCase()) })
  const total = servidor ? res?.total ?? 0 : t.getFilteredRowModel().rows.length
  const { pageIndex, pageSize } = t.getState().pagination
  const nPag = Math.max(1, Math.ceil(total / pageSize))
  if (servidor) { error = error || sErr; cargando = sCarga; reintentar = reintentar ?? pedir }
  const conBarra = buscar || chips || acciones || titulo
  return <div className="ds-table rounded-card border border-line bg-surface" data-testid={testid}>
    {conBarra && <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
      {titulo && <div className="mr-auto text-sm font-semibold text-fg">{titulo}</div>}
      {chips}
      <div className={cn('flex flex-wrap items-center gap-2', !titulo && 'ml-auto')}>
        {buscar && <label className="relative flex items-center"><span className="sr-only">Buscar</span>
          <Search size={15} className="pointer-events-none absolute left-2.5 text-muted" aria-hidden />
          <input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder={buscar} className="ds-input h-9 w-56 !pl-8" /></label>}
        {acciones}
      </div>
    </div>}
    {error ? <div className="p-4"><ErrorBox msg={error} reintentar={reintentar} /></div>
      : cargando && filas.length === 0 ? <Cargando />
      : total === 0 ? <Vacio texto={q ? `Sin resultados para “${q}”.` : (vacio ?? 'Sin registros.')} />
      : <div className="overflow-x-auto"><table className={cn('ds-dt w-full border-collapse text-sm', servidor && cargando && 'opacity-60')} aria-busy={cargando || undefined}>
        <thead>{t.getHeaderGroups().map(hg => <tr key={hg.id}>{hg.headers.map(h => {
          const s = h.column.getIsSorted(); const puede = h.column.getCanSort() && !h.isPlaceholder
          return <th key={h.id} aria-sort={s === 'asc' ? 'ascending' : s === 'desc' ? 'descending' : undefined}
            className="whitespace-nowrap border-b border-line bg-surface-2 px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-muted">
            {h.isPlaceholder ? null : puede ? <button type="button" onClick={h.column.getToggleSortingHandler()}
              className="inline-flex items-center gap-1 border-0 bg-transparent p-0 text-xs font-medium uppercase tracking-wide text-muted cursor-pointer hover:text-fg">
              {flexRender(h.column.columnDef.header, h.getContext())}
              {s === 'asc' ? <ArrowUp size={12} /> : s === 'desc' ? <ArrowDown size={12} /> : <ArrowUpDown size={12} className="opacity-40" />}</button>
              : flexRender(h.column.columnDef.header, h.getContext())}</th>
        })}</tr>)}</thead>
        <tbody>{t.getRowModel().rows.map(r => <tr key={r.id} className={cn('border-b border-line last:border-0 hover:bg-surface-2/60', filaClase?.(r.original))}>
          {r.getVisibleCells().map(c => <td key={c.id} className={cn('px-3 align-middle text-fg', compacta ? 'py-1.5' : 'py-2.5')}>{flexRender(c.column.columnDef.cell, c.getContext())}</td>)}</tr>)}</tbody>
      </table></div>}
    {(total > Math.min(pageSize, tamanos[0]) || pageIndex > 0) && <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5 text-xs text-muted">
      <span aria-live="polite">{rango(pageIndex + 1, pageSize, total)}</span>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1.5">Filas
          <select className="ds-input h-8 !w-auto !py-0" value={pageSize} onChange={e => t.setPagination({ pageIndex: 0, pageSize: Number(e.target.value) })}>
            {[...new Set([...tamanos, tam])].sort((a, b) => a - b).map(n => <option key={n} value={n}>{n}</option>)}</select></label>
        <nav className="flex items-center gap-1" aria-label="Paginación">
          <button type="button" aria-label="Primera página" disabled={pageIndex === 0} onClick={() => t.setPageIndex(0)} className="ds-pg"><ChevronsLeft size={14} /></button>
          <button type="button" aria-label="Página anterior" disabled={pageIndex === 0} onClick={() => t.setPageIndex(pageIndex - 1)} className="ds-pg"><ChevronLeft size={14} /></button>
          {paginas(pageIndex + 1, nPag).map((n, i) => n === '…' ? <span key={`e${i}`} className="px-1">…</span>
            : <button type="button" key={n} aria-label={`Página ${n}`} aria-current={n === pageIndex + 1 ? 'page' : undefined} onClick={() => t.setPageIndex(n - 1)}
              className={cn('ds-pg', n === pageIndex + 1 && '!border-primary !bg-primary !text-primary-fg')}>{n}</button>)}
          <button type="button" aria-label="Página siguiente" disabled={pageIndex + 1 >= nPag} onClick={() => t.setPageIndex(pageIndex + 1)} className="ds-pg"><ChevronRight size={14} /></button>
          <button type="button" aria-label="Última página" disabled={pageIndex + 1 >= nPag} onClick={() => t.setPageIndex(nPag - 1)} className="ds-pg"><ChevronsRight size={14} /></button>
        </nav>
      </div>
    </div>}
  </div>
}
