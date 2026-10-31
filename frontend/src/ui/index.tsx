import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { twMerge } from 'tailwind-merge'
import { AlertCircle, Inbox, Loader2, Minus, Moon, RefreshCw, Sun, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import { useTheme } from '../theme/useTheme'

export const cn = (...c: (string | false | null | undefined)[]) => twMerge(c.filter(Boolean).join(' '))

export function Card({ className, children, ...p }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div {...p} className={cn('ds-card rounded-card border border-line bg-surface p-4 shadow-[0_1px_2px_rgba(16,6,28,.06)]', className)}>{children}</div>
}

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export function Button({ variant = 'secondary', size = 'md', icon: Icon, className, children, ...p }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: 'sm' | 'md'; icon?: LucideIcon }) {
  const v: Record<BtnVariant, string> = {
    primary: 'bg-primary text-primary-fg border-primary hover:opacity-90',
    secondary: 'bg-surface text-fg border-line hover:bg-surface-2',
    ghost: 'bg-transparent text-muted border-transparent hover:bg-surface-2 hover:text-fg',
    danger: 'bg-danger-bg text-danger border-transparent hover:opacity-90',
  }
  return <button type="button" {...p} className={cn('ds-btn inline-flex items-center justify-center gap-2 rounded-ctl border font-medium cursor-pointer transition disabled:cursor-not-allowed disabled:opacity-50',
    size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-2 text-sm', v[variant], className)}>
    {Icon && <Icon size={size === 'sm' ? 14 : 16} aria-hidden />}{children}</button>
}

export type Tono = 'success' | 'warning' | 'danger' | 'neutral' | 'accent'
const TONO: Record<Tono, string> = { success: 'bg-success-bg text-success', warning: 'bg-warning-bg text-warning', danger: 'bg-danger-bg text-danger',
  neutral: 'bg-surface-2 text-muted', accent: 'bg-accent-soft text-accent' }
export function Pill({ tono = 'neutral', children, className }: { tono?: Tono; children: ReactNode; className?: string }) {
  return <span className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONO[tono], className)}>
    <span className="size-1.5 rounded-full bg-current" aria-hidden />{children}</span>
}
/** Mapea estados de dominio a tonos de pill (ámbar/verde/rojo). */
export function tonoEstado(e: string | null | undefined): Tono {
  const s = String(e ?? '').toLowerCase()
  if (/(aprob|pagad|ok|cerrad|dentro|activo|vigente|leida|registrada|program|exportad|complet|sincron)/.test(s)) return 'success'
  if (/(rechaz|fuera|error|anulad|inactiv|venc|falta)/.test(s)) return 'danger'
  if (/(pend|regist|abiert|diferid|sin_gps|alerta|borrador|prelim|reabiert|proceso)/.test(s)) return 'warning'
  return 'neutral'
}
export const PillEstado = ({ estado }: { estado: string | null | undefined }) => <Pill tono={tonoEstado(estado)}>{String(estado ?? '—').replace(/_/g, ' ')}</Pill>

export type Status = 'pagado' | 'pendiente' | 'rechazado'
export function StatusPill({ status }: { status: Status }) {
  return <Pill tono={{ pagado: 'success', pendiente: 'warning', rechazado: 'danger' }[status] as Tono} className="capitalize">{status}</Pill>
}

export type Acento = 'accent' | 'amber' | 'teal' | 'danger'
export function KpiCard({ icon: Icon, label, value, delta, accent = 'accent', invertir = false, sub = 'vs. periodo anterior' }:
  { icon: LucideIcon; label: string; value: string; delta?: number | null; accent?: Acento; invertir?: boolean; sub?: string }) {
  const a = { accent: 'text-accent bg-accent-soft', amber: 'text-amber bg-warning-bg', teal: 'text-teal bg-surface-2', danger: 'text-danger bg-danger-bg' }[accent]
  const hay = delta != null && Number.isFinite(delta)
  const bueno = hay && (invertir ? delta! <= 0 : delta! >= 0)
  return <Card className="flex flex-col gap-3" data-kpi={label}>
    <div className="flex items-center gap-2.5 text-sm font-medium text-muted">
      <span className={cn('grid size-9 place-items-center rounded-ctl', a)}><Icon size={18} aria-hidden /></span>{label}
    </div>
    <div className="flex items-end justify-between gap-2">
      <span className="text-[28px] font-semibold leading-none tracking-tight text-fg">{value}</span>
      {hay ? <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold', bueno ? 'bg-success-bg text-success' : 'bg-danger-bg text-danger')}>
        {delta! >= 0 ? <TrendingUp size={12} aria-hidden /> : <TrendingDown size={12} aria-hidden />}{delta! >= 0 ? '+' : ''}{delta!.toFixed(1)}%
      </span> : delta === undefined ? null : <span className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted"><Minus size={12} aria-hidden />s/d</span>}
    </div>
    <div className="text-xs text-muted">{sub}</div>
  </Card>
}

export function SidebarItem({ icon: Icon, label, count, active, onClick }:
  { icon: LucideIcon; label: string; count?: number; active?: boolean; onClick?: () => void }) {
  return <button onClick={onClick} aria-current={active ? 'page' : undefined}
    className={cn('flex w-full items-center gap-3 rounded-ctl border-0 px-3 py-2 text-sm cursor-pointer text-left',
      active ? 'bg-sidebar-active text-sidebar-fg font-semibold' : 'bg-transparent text-sidebar-muted hover:text-sidebar-fg hover:bg-white/5')}>
    <Icon size={16} aria-hidden /><span className="flex-1">{label}</span>
    {count != null && <span className="rounded-full bg-white/10 px-2 text-xs">{count}</span>}
  </button>
}

export function Segmented<T extends string>({ options, value, onChange, label, labels }:
  { options: readonly T[]; value: T; onChange: (v: T) => void; label: string; labels?: Partial<Record<T, string>> }) {
  return <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap rounded-ctl border border-line bg-surface-2 p-0.5">
    {options.map(o => <button type="button" key={o} role="radio" aria-checked={o === value} onClick={() => onChange(o)}
      className={cn('rounded-lg border-0 px-3 py-1.5 text-sm cursor-pointer', o === value ? 'bg-surface text-fg font-semibold shadow-sm' : 'bg-transparent text-muted hover:text-fg')}>{labels?.[o] ?? o}</button>)}
  </div>
}

export function ThemeToggle() {
  const [t, toggle] = useTheme()
  const next = t === 'dark' ? 'claro' : 'oscuro'
  return <Button variant="ghost" onClick={toggle} aria-label={`Cambiar a modo ${next}`} title={`Modo ${next}`} icon={t === 'dark' ? Sun : Moon} />
}

/** Encabezado de pantalla: h2 (los e2e buscan estos títulos), descripción y acciones. */
export function PageHeader({ titulo, desc, children, icon: Icon }: { titulo: ReactNode; desc?: ReactNode; children?: ReactNode; icon?: LucideIcon }) {
  return <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
    <div className="flex min-w-0 items-start gap-3">
      {Icon && <span className="mt-0.5 hidden size-10 place-items-center rounded-card bg-accent-soft text-accent sm:grid"><Icon size={20} aria-hidden /></span>}
      <div className="min-w-0"><h2 className="!m-0 text-xl font-semibold tracking-tight text-fg">{titulo}</h2>
        {desc && <p className="m-0 mt-1 max-w-3xl text-sm text-muted">{desc}</p>}</div>
    </div>
    {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
  </div>
}

/** Pantalla: contenedor vertical sin fondo (las tarjetas van dentro). */
export const Pantalla = ({ children, className }: { children: ReactNode; className?: string }) =>
  <section className={cn('pantalla flex flex-col gap-4', className)}>{children}</section>

export const Toolbar = ({ children, className }: { children: ReactNode; className?: string }) =>
  <div className={cn('flex flex-wrap items-end gap-3', className)}>{children}</div>

/** Campo con label envolvente (getByLabel sigue funcionando). */
export function Field({ label, error, children, className, hint }: { label: ReactNode; error?: string; children: ReactNode; className?: string; hint?: string }) {
  return <label className={cn('ds-field flex flex-col gap-1 text-xs font-medium text-muted', className)}>{label}{children}
    {hint && !error && <span className="font-normal text-muted">{hint}</span>}
    {error && <span className="font-normal text-danger" role="alert">{error}</span>}</label>
}

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return <div role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-muted"><Loader2 size={18} className="animate-spin" aria-hidden />{texto}</div>
}
export function Vacio({ texto = 'Sin datos para mostrar.', icon: Icon = Inbox, children }: { texto?: string; icon?: LucideIcon; children?: ReactNode }) {
  return <div className="flex flex-col items-center justify-center gap-2 py-10 text-center text-sm text-muted">
    <span className="grid size-11 place-items-center rounded-full bg-surface-2"><Icon size={20} aria-hidden /></span><p className="m-0">{texto}</p>{children}</div>
}
export function ErrorBox({ msg, reintentar }: { msg: string; reintentar?: () => void }) {
  return <div role="alert" className="flex flex-wrap items-center gap-3 rounded-ctl border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger">
    <AlertCircle size={16} aria-hidden /><span className="flex-1">{msg}</span>
    {reintentar && <Button size="sm" variant="ghost" icon={RefreshCw} onClick={reintentar} className="text-danger">Reintentar</Button>}</div>
}
export function Aviso({ tono = 'warning', children, className }: { tono?: Tono; children: ReactNode; className?: string }) {
  return <div className={cn('rounded-ctl px-3 py-2 text-sm', TONO[tono], className)}>{children}</div>
}
