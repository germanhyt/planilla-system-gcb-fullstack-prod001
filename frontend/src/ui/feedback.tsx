// Feedback global: toasts (react-toastify) y diálogos Headless UI con API de promesa (reemplazan alert/confirm/prompt).
import { useEffect, useState } from 'react'
import { Dialog, DialogPanel, DialogTitle } from '@headlessui/react'
import { Slide, toast, ToastContainer } from 'react-toastify'
import { Button, cn } from '.'

export { toast }
export const ok = (m: string) => toast.success(m)
export const fallo = (e: unknown) => toast.error(e instanceof Error ? e.message : String(e))

export function Toaster() {
  return <ToastContainer position="bottom-right" autoClose={4000} newestOnTop closeOnClick transition={Slide} theme="light" toastClassName="ds-toast" />
}

type Pedido = { tipo: 'confirm' | 'prompt'; titulo: string; mensaje?: string; label?: string; min?: number; peligro?: boolean; ok?: string; opcional?: boolean
  resolver: (v: any) => void }
let abrir: ((p: Pedido) => void) | null = null

export function confirmar(o: { titulo: string; mensaje?: string; peligro?: boolean; ok?: string }): Promise<boolean> {
  return new Promise(r => abrir ? abrir({ tipo: 'confirm', ...o, resolver: r }) : r(window.confirm(o.titulo)))
}
/** Pide un texto (p.ej. motivo). Devuelve null si se cancela. */
export function pedirTexto(o: { titulo: string; mensaje?: string; label: string; min?: number; opcional?: boolean; ok?: string; peligro?: boolean }): Promise<string | null> {
  return new Promise(r => abrir ? abrir({ tipo: 'prompt', ...o, resolver: r }) : r(window.prompt(o.titulo)))
}

export function DialogHost() {
  const [p, setP] = useState<Pedido | null>(null); const [txt, setTxt] = useState('')
  useEffect(() => { abrir = x => { setTxt(''); setP(x) }; return () => { abrir = null } }, [])
  const cerrar = (v: any) => { p?.resolver(v); setP(null) }
  const corto = p?.tipo === 'prompt' && !p.opcional && txt.trim().length < (p.min ?? 1)
  return <Dialog open={!!p} onClose={() => cerrar(p?.tipo === 'prompt' ? null : false)} className="ds relative z-[60]">
    <div className="fixed inset-0 bg-black/50" aria-hidden />
    <div className="fixed inset-0 grid place-items-center p-4">
      <DialogPanel className="w-full max-w-md rounded-card border border-line bg-surface p-5 shadow-2xl">
        <DialogTitle className="m-0 text-base font-semibold text-fg">{p?.titulo}</DialogTitle>
        {p?.mensaje && <p className="mb-0 mt-2 text-sm text-muted">{p.mensaje}</p>}
        {p?.tipo === 'prompt' && <form onSubmit={e => { e.preventDefault(); if (!corto) cerrar(txt.trim()) }}>
          <label className="mt-3 flex flex-col gap-1 text-xs font-medium text-muted">{p.label}
            <textarea autoFocus rows={3} value={txt} onChange={e => setTxt(e.target.value)} className="ds-input resize-y" /></label>
          {p.min && p.min > 1 && <p className="m-0 mt-1 text-xs text-muted">Mínimo {p.min} caracteres ({txt.trim().length}).</p>}
        </form>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => cerrar(p?.tipo === 'prompt' ? null : false)}>Cancelar</Button>
          <Button variant={p?.peligro ? 'danger' : 'primary'} disabled={corto} className={cn(p?.peligro && 'border-danger')}
            onClick={() => cerrar(p?.tipo === 'prompt' ? txt.trim() : true)}>{p?.ok ?? 'Confirmar'}</Button>
        </div>
      </DialogPanel>
    </div>
  </Dialog>
}

/** Modal genérico (formularios, historiales). */
export function Modal({ abierto, onClose, titulo, children, ancho = 'max-w-2xl' }: { abierto: boolean; onClose: () => void; titulo: string; children: React.ReactNode; ancho?: string }) {
  return <Dialog open={abierto} onClose={onClose} className="ds relative z-50">
    <div className="fixed inset-0 bg-black/50" aria-hidden />
    <div className="fixed inset-0 overflow-y-auto p-4"><div className="grid min-h-full place-items-center">
      <DialogPanel className={cn('w-full rounded-card border border-line bg-surface p-5 shadow-2xl', ancho)}>
        <DialogTitle className="m-0 mb-4 text-base font-semibold text-fg">{titulo}</DialogTitle>{children}
      </DialogPanel></div></div>
  </Dialog>
}
