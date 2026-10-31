import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, Bell, Boxes, Building2, CalendarDays, ChartColumn, ChevronDown, ChevronsLeft, ChevronsRight, Clock, FileText, Fingerprint,
  List, Lock, LogOut, MapPin, Menu, Moon, PiggyBank, Scale, ScrollText, Settings, Shield, Timer, User, Users, X, type LucideIcon } from 'lucide-react'
import { api } from '../api'
import { cn, ThemeToggle } from '../ui'
import { construirMenu, migas, puedeFiltrarEmpresa } from './menuLib'
import { textoBadge } from '../trabajosLib'

const ICON: Record<string, LucideIcon> = { user: User, fingerprint: Fingerprint, list: List, bell: Bell, piggy: PiggyBank, clock: Clock, calendar: CalendarDays,
  timer: Timer, file: FileText, alert: AlertTriangle, chart: ChartColumn, moon: Moon, lock: Lock, scale: Scale, building: Building2, boxes: Boxes, map: MapPin,
  contract: ScrollText, users: Users, shield: Shield, settings: Settings }
const KEY_COLAPSO = 'gcb-sidebar-collapsed', KEY_EMPRESA = 'gcb-empresa-filtro'
const salir = () => { localStorage.removeItem('token'); location.reload() }

function FiltroEmpresa() {
  const [emps, setEmps] = useState<any[]>([]); const [v, setV] = useState(() => localStorage.getItem(KEY_EMPRESA) || '')
  useEffect(() => { api('/empresas').then(setEmps).catch(() => {}) }, [])
  return <select aria-label="Filtrar por empresa" value={v} onChange={e => { setV(e.target.value); localStorage.setItem(KEY_EMPRESA, e.target.value) }}
    className="hidden h-9 max-w-[220px] rounded-ctl border border-line bg-surface px-2 text-sm text-fg sm:block">
    <option value="">Todas las empresas</option>{emps.map(e => <option key={e.id} value={e.id}>{e.razon_social}</option>)}</select>
}

function MenuUsuario({ me }: { me: any }) {
  const [abierto, setAbierto] = useState(false); const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { const f = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setAbierto(false) }; document.addEventListener('mousedown', f); return () => document.removeEventListener('mousedown', f) }, [])
  const ini = (me.nombre || '?').split(' ').map((s: string) => s[0]).slice(0, 2).join('').toUpperCase()
  return <div ref={ref} className="relative">
    <button aria-label="Menú de usuario" aria-expanded={abierto} onClick={() => setAbierto(!abierto)}
      className="flex items-center gap-2 rounded-ctl border border-transparent bg-transparent px-1.5 py-1 text-fg cursor-pointer hover:bg-surface-2">
      <span className="grid size-8 place-items-center rounded-full bg-primary text-xs font-bold text-primary-fg">{ini}</span>
      <span className="hidden text-left leading-tight md:block"><span className="block text-sm font-semibold">{me.nombre}</span><span className="block text-xs text-muted">{me.rol}</span></span>
      <ChevronDown size={14} className="hidden text-muted md:block" aria-hidden />
    </button>
    {abierto && <div role="menu" className="absolute right-0 z-50 mt-2 w-56 rounded-card border border-line bg-surface p-1 shadow-lg">
      <div className="px-3 py-2 text-xs text-muted">{me.email}</div>
      <button role="menuitem" onClick={salir} className="flex w-full items-center gap-2 rounded-ctl border-0 bg-transparent px-3 py-2 text-left text-sm text-danger cursor-pointer hover:bg-danger-bg">
        <LogOut size={16} aria-hidden />Salir</button>
    </div>}
  </div>
}

export function Shell({ me, vista, setVista, noLeidas, children }:
  { me: any; vista: string; setVista: (v: string) => void; noLeidas: number; children: ReactNode }) {
  const grupos = construirMenu(me.rol)
  const [colapsado, setColapsado] = useState(() => localStorage.getItem(KEY_COLAPSO) === '1')
  const [drawer, setDrawer] = useState(false)
  const [g, actual] = migas(grupos, vista)
  const ir = (k: string) => { setVista(k); setDrawer(false) }
  const trabajador = me.rol === 'trabajador'
  const colapsar = () => { const n = !colapsado; setColapsado(n); localStorage.setItem(KEY_COLAPSO, n ? '1' : '0') }
  return <div className="ds app-shell flex min-h-screen">
    {drawer && <div className="fixed inset-0 z-30 bg-black/50 md:hidden" onClick={() => setDrawer(false)} aria-hidden />}
    <aside className={cn('fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-surface-2 transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0',
      drawer ? 'translate-x-0' : '-translate-x-full', colapsado && 'md:w-[72px]')}>
      <div className="flex h-14 items-center gap-2 px-4">
        <img src="/brand/logo-mark-dark-bg.png" alt="GCB" className="logo-dark h-6" /><img src="/brand/logo-mark-light-bg.png" alt="GCB" className="logo-light h-6" />
        <span className={cn('text-sm font-semibold', colapsado && 'md:hidden')}>Planillas</span>
        <button aria-label="Cerrar menú" onClick={() => setDrawer(false)} className="ml-auto rounded-ctl border-0 bg-transparent p-1 text-muted md:hidden"><X size={18} /></button>
      </div>
      <nav aria-label="Menú principal" className="flex-1 overflow-y-auto px-3 pb-3">
        {grupos.map(gr => <div key={gr.titulo} className="mb-3">
          <div className={cn('px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-muted', colapsado && 'md:sr-only')}>{gr.titulo}</div>
          {gr.items.map(it => { const Icon = ICON[it.icon] || User; const act = vista === it.k
            return <button key={it.k} onClick={() => ir(it.k)} aria-current={act ? 'page' : undefined} title={colapsado ? it.label : undefined}
              className={cn('act-pill mb-0.5 flex w-full items-center gap-3 rounded-ctl border px-3 py-2 text-left text-sm cursor-pointer', act ? 'act border-line bg-pill-active font-semibold text-fg shadow-sm' : 'border-transparent bg-transparent text-muted hover:bg-surface hover:text-fg', colapsado && 'md:justify-center md:px-0')}>
              <Icon size={18} aria-hidden className="shrink-0" /><span className={cn('flex-1', colapsado && 'md:sr-only')}>{it.label}</span>
              {it.k === 'notificaciones' && noLeidas > 0 && <b data-testid="badge-notif" className="rounded-full bg-danger px-1.5 text-[11px] font-bold text-surface">{textoBadge(noLeidas)}</b>}
            </button> })}
        </div>)}
      </nav>
      <button onClick={colapsar} aria-label={colapsado ? 'Expandir menú' : 'Contraer menú'} className="m-3 hidden items-center justify-center gap-2 rounded-ctl border border-line bg-surface py-2 text-xs text-muted cursor-pointer md:flex">
        {colapsado ? <ChevronsRight size={16} /> : <><ChevronsLeft size={16} />Contraer</>}</button>
    </aside>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-line bg-bg/90 px-3 backdrop-blur md:px-5">
        <button aria-label="Abrir menú" onClick={() => setDrawer(true)} className="rounded-ctl border border-line bg-surface p-2 text-fg md:hidden"><Menu size={18} /></button>
        <div aria-label="Ruta" className="min-w-0 truncate text-sm text-muted"><span className="hidden sm:inline">{g} / </span><span className="font-semibold text-fg">{actual}</span></div>
        <div className="ml-auto flex items-center gap-1.5">
          {puedeFiltrarEmpresa(me.rol) && <FiltroEmpresa />}
          {puedeFiltrarEmpresa(me.rol) && <button aria-label="Ver notificaciones" onClick={() => ir('notificaciones')} className="relative rounded-ctl border-0 bg-transparent p-2 text-muted cursor-pointer hover:bg-surface-2 hover:text-fg">
            <Bell size={18} aria-hidden />{noLeidas > 0 && <span className="absolute right-1 top-1 size-2 rounded-full bg-danger" />}</button>}
          <ThemeToggle /><MenuUsuario me={me} />
        </div>
      </header>
      <main className={cn('app-main min-w-0 flex-1 p-3 md:p-6', trabajador && 'pb-24 md:pb-6')}>{children}</main>
    </div>
    {trabajador && <div className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-3 gap-2 border-t border-line bg-surface p-2 md:hidden" aria-label="Accesos rápidos">
      {([['marcar', 'Marcar', Fingerprint], ['mis-marcas', 'Mis marcas', List]] as const).map(([k, l, I]) =>
        <button key={k} onClick={() => ir(k)} className={cn('flex min-h-14 flex-col items-center justify-center gap-1 rounded-card border-0 text-xs font-semibold cursor-pointer', vista === k ? 'bg-primary text-primary-fg' : 'bg-surface-2 text-fg')}><I size={22} aria-hidden />{l}</button>)}
      <button onClick={() => setDrawer(true)} className="flex min-h-14 flex-col items-center justify-center gap-1 rounded-card border-0 bg-surface-2 text-xs font-semibold text-fg cursor-pointer"><Menu size={22} aria-hidden />Más</button>
    </div>}
  </div>
}
