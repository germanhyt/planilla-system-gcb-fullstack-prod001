import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { twMerge } from 'tailwind-merge'
import { Moon, Sun, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import { useTheme } from '../theme/useTheme'

export const cn = (...c: (string | false | null | undefined)[]) => twMerge(c.filter(Boolean).join(' '))

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn('rounded-card border border-line bg-surface p-4', className)}>{children}</div>
}

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export function Button({ variant = 'secondary', icon: Icon, className, children, ...p }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; icon?: LucideIcon }) {
  const v: Record<BtnVariant, string> = {
    primary: 'bg-primary text-primary-fg border-primary hover:opacity-90',
    secondary: 'bg-surface text-fg border-line hover:bg-surface-2',
    ghost: 'bg-transparent text-muted border-transparent hover:bg-surface-2 hover:text-fg',
    danger: 'bg-danger-bg text-danger border-transparent hover:opacity-90',
  }
  return <button {...p} className={cn('inline-flex items-center gap-2 rounded-ctl border px-3 py-2 text-sm font-medium cursor-pointer transition disabled:opacity-50', v[variant], className)}>
    {Icon && <Icon size={16} aria-hidden />}{children}</button>
}

export type Status = 'pagado' | 'pendiente' | 'rechazado'
export function StatusPill({ status }: { status: Status }) {
  const s = { pagado: 'bg-success-bg text-success', pendiente: 'bg-warning-bg text-warning', rechazado: 'bg-danger-bg text-danger' }[status]
  return <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize', s)}>
    <span className="size-1.5 rounded-full bg-current" aria-hidden />{status}</span>
}

export function KpiCard({ icon: Icon, label, value, delta, accent = 'blue' }:
  { icon: LucideIcon; label: string; value: string; delta: number; accent?: 'blue' | 'amber' | 'teal' }) {
  const up = delta >= 0
  const a = { blue: 'text-blue', amber: 'text-amber', teal: 'text-teal' }[accent]
  return <Card>
    <div className="flex items-center gap-2 text-sm text-muted">
      <span className={cn('grid size-8 place-items-center rounded-ctl bg-surface-2', a)}><Icon size={16} aria-hidden /></span>{label}
    </div>
    <div className="mt-3 flex items-end justify-between">
      <span className="text-3xl font-semibold tracking-tight">{value}</span>
      <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold', up ? 'bg-success-bg text-success' : 'bg-danger-bg text-danger')}>
        {up ? <TrendingUp size={12} aria-hidden /> : <TrendingDown size={12} aria-hidden />}{up ? '+' : ''}{delta.toFixed(1)}%
      </span>
    </div>
    <div className="mt-1 text-xs text-muted">vs. periodo anterior</div>
  </Card>
}

export function SidebarItem({ icon: Icon, label, count, active, onClick }:
  { icon: LucideIcon; label: string; count?: number; active?: boolean; onClick?: () => void }) {
  return <button onClick={onClick} aria-current={active ? 'page' : undefined}
    className={cn('flex w-full items-center gap-3 rounded-ctl border px-3 py-2 text-sm cursor-pointer text-left',
      active ? 'border-line bg-pill-active text-fg font-semibold shadow-sm' : 'border-transparent bg-transparent text-muted hover:text-fg hover:bg-surface-2')}>
    <Icon size={16} aria-hidden /><span className="flex-1">{label}</span>
    {count != null && <span className="rounded-full bg-surface-2 px-2 text-xs text-muted">{count}</span>}
  </button>
}

export function Segmented<T extends string>({ options, value, onChange, label }: { options: T[]; value: T; onChange: (v: T) => void; label: string }) {
  return <div role="radiogroup" aria-label={label} className="inline-flex rounded-ctl border border-line bg-surface-2 p-0.5">
    {options.map(o => <button key={o} role="radio" aria-checked={o === value} onClick={() => onChange(o)}
      className={cn('rounded-lg border-0 px-3 py-1.5 text-sm cursor-pointer', o === value ? 'bg-surface text-fg font-semibold shadow-sm' : 'bg-transparent text-muted')}>{o}</button>)}
  </div>
}

export function ThemeToggle() {
  const [t, toggle] = useTheme()
  const next = t === 'dark' ? 'claro' : 'oscuro'
  return <Button variant="ghost" onClick={toggle} aria-label={`Cambiar a modo ${next}`} title={`Modo ${next}`} icon={t === 'dark' ? Sun : Moon} />
}
