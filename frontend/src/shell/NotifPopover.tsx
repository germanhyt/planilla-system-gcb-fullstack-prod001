// Campana de notificaciones: panel fijo (popover en escritorio, hoja inferior en móvil) con no leídas, marcar leída / todas y "Ver todas".
import { useEffect, useRef, useState } from 'react'
import { Bell, CheckCheck, Check, X } from 'lucide-react'
import { api } from '../api'
import { cn, Pill } from '../ui'
import { fallo } from '../ui/feedback'
import { conEmpresa, useEmpresaFiltro } from '../ui/empresaFiltro'
import { textoBadge } from '../trabajosLib'

type N = { id: number; periodo: string; tipo: string; mensaje: string; leida: boolean; creada_en: string | null }

export function NotifPopover({ noLeidas, onCambio, verTodas }: { noLeidas: number; onCambio: () => void; verTodas: () => void }) {
  const [abierto, setAbierto] = useState(false); const [lista, setLista] = useState<N[] | null>(null); const [err, setErr] = useState('')
  const empresa = useEmpresaFiltro(); const ref = useRef<HTMLDivElement>(null)
  const cargar = () => { setErr(''); api<{ items: N[] }>(`/notificaciones?${conEmpresa({ page: 1, page_size: 8 }, empresa)}`).then(r => setLista(r.items)).catch(e => setErr(e.message)) }
  useEffect(() => { if (abierto) cargar() }, [abierto, empresa, noLeidas])
  useEffect(() => {
    if (!abierto) return
    const fuera = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setAbierto(false) }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setAbierto(false)
    document.addEventListener('mousedown', fuera); document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', esc) }
  }, [abierto])
  const leer = async (id: number) => { try { await api(`/notificaciones/${id}/leida`, { method: 'POST' }); setLista(l => l?.map(n => n.id === id ? { ...n, leida: true } : n) ?? null); onCambio() } catch (e) { fallo(e) } }
  const leerTodas = async () => { try { await api(`/notificaciones/leer-todas?${conEmpresa({}, empresa)}`, { method: 'POST' }); setLista(l => l?.map(n => ({ ...n, leida: true })) ?? null); onCambio() } catch (e) { fallo(e) } }
  return <div ref={ref}>
    <button aria-label="Ver notificaciones" aria-expanded={abierto} aria-haspopup="dialog" onClick={() => setAbierto(!abierto)}
      className="relative rounded-ctl border-0 bg-transparent p-2 text-muted cursor-pointer hover:bg-surface-2 hover:text-fg">
      <Bell size={18} aria-hidden />{noLeidas > 0 && <span data-testid="badge-campana" className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-danger px-1 text-center text-[10px] font-bold leading-4 text-white">{textoBadge(noLeidas)}</span>}</button>
    {abierto && <div role="dialog" aria-label="Notificaciones" className="fixed inset-x-2 bottom-2 z-50 flex max-h-[75vh] flex-col overflow-hidden rounded-card border border-line bg-surface shadow-2xl sm:inset-x-auto sm:bottom-auto sm:right-4 sm:top-16 sm:w-96">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <p className="m-0 font-semibold text-fg">Notificaciones</p>{noLeidas > 0 && <Pill tono="danger">{noLeidas} sin leer</Pill>}
        <button aria-label="Cerrar notificaciones" onClick={() => setAbierto(false)} className="ml-auto rounded-ctl border-0 bg-transparent p-1 text-muted cursor-pointer hover:text-fg"><X size={16} /></button>
      </div>
      <div className="ds-scroll flex-1 overflow-y-auto">
        {err ? <p className="m-0 p-4 text-sm text-danger">{err}</p> : !lista ? <p className="m-0 p-4 text-sm text-muted">Cargando…</p>
          : lista.length === 0 ? <p className="m-0 p-6 text-center text-sm text-muted">No hay notificaciones activas.</p>
          : <ul className="m-0 list-none p-0">{lista.map(n => <li key={n.id} className={cn('flex gap-3 border-b border-line px-4 py-3 last:border-0', !n.leida && 'bg-accent-soft/40')}>
            <span className={cn('mt-1.5 size-2 shrink-0 rounded-full', n.leida ? 'bg-transparent' : 'bg-accent')} aria-hidden />
            <div className="min-w-0 flex-1 text-sm"><p className="m-0 text-fg">{n.mensaje}</p>
              <p className="m-0 mt-0.5 text-xs text-muted">{n.periodo} · {n.tipo.replace(/_/g, ' ')}{n.leida && ' · leída'}</p></div>
            {!n.leida && <button aria-label="Marcar como leída" title="Marcar como leída" onClick={() => leer(n.id)} className="h-7 shrink-0 rounded-ctl border border-line bg-surface p-1 text-muted cursor-pointer hover:text-accent"><Check size={14} /></button>}
          </li>)}</ul>}
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-2.5">
        <button onClick={leerTodas} disabled={!noLeidas} className="inline-flex items-center gap-1.5 rounded-ctl border-0 bg-transparent p-1 text-xs font-medium text-accent cursor-pointer disabled:cursor-default disabled:opacity-50"><CheckCheck size={14} />Marcar todas como leídas</button>
        <button onClick={() => { setAbierto(false); verTodas() }} className="rounded-ctl border-0 bg-primary px-3 py-1.5 text-xs font-semibold text-primary-fg cursor-pointer">Ver todas</button>
      </div>
    </div>}
  </div>
}
