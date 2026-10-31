import { useEffect, useMemo, useState } from 'react'
import { Eye, Send, Settings } from 'lucide-react'
import { api } from './api'
import { Aviso, Button, Card, PageHeader, Pantalla, Pill, cn } from './ui'
import { confirmar, ok } from './ui/feedback'
import { Crud, Campo } from './Crud'
import { aplicar, CAMPOS_REGLA, Cambio, convertir, erroresGenerales, erroresPorCampo, leer, validarLocal } from './configLib'

const hoyLima = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const fmt = (v: unknown) => (v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))

export function Configuracion({ admin, contrato }: { admin: boolean; contrato: Campo[] }) {
  const [tab, setTab] = useState<'reglas' | 'contratos'>('reglas')
  const pest = (k: typeof tab, l: string) => <button type="button" aria-pressed={tab === k} onClick={() => setTab(k)}
    className={cn('rounded-ctl px-3 py-1.5 text-sm font-medium', tab === k ? 'act bg-primary text-primary-fg' : 'text-muted hover:bg-surface-2')}>{l}</button>
  return <Pantalla><PageHeader titulo="Configuración" icon={Settings} desc="Reglas versionadas por empresa (inmutables, con vigencia) y catálogos de contrato." />
    {!admin && <Aviso tono="accent">Solo lectura: los cambios de configuración los publica un administrador.</Aviso>}
    <nav aria-label="Secciones de configuración" className="inline-flex w-fit gap-1 rounded-card border border-border bg-surface p-1">{pest('reglas', 'Reglas por empresa')}{pest('contratos', 'Tipos de contrato')}</nav>
    {tab === 'reglas' ? <ReglasEmpresa admin={admin} /> : <Crud titulo="Tipos de contrato" ruta="/tipos-contrato" campos={contrato} puedeEscribir={admin} />}
  </Pantalla>
}

function ReglasEmpresa({ admin }: { admin: boolean }) {
  const [emps, setEmps] = useState<any[]>([]); const [emp, setEmp] = useState<number | null>(null)
  const [hist, setHist] = useState<any[]>([]); const [vig, setVig] = useState<any>(null)
  const [valores, setValores] = useState<Record<string, unknown>>({})
  const [validFrom, setValidFrom] = useState(''); const [motivo, setMotivo] = useState('')
  const [errores, setErrores] = useState<Record<string, string>>({}); const [msg, setMsg] = useState('')
  const [cambios, setCambios] = useState<Cambio[] | null>(null); const [contra, setContra] = useState<number | null>(null)

  useEffect(() => { api('/empresas').then(e => { setEmps(e); if (e[0]) setEmp(e[0].id) }) }, [])
  const cargar = (id: number) => {
    setCambios(null); setErrores({}); setMsg('')
    api(`/rule-sets?empresa_id=${id}`).then(h => setHist([...h].sort((a, b) => b.version - a.version)))
    api(`/rule-sets/vigente?empresa_id=${id}&fecha=${hoyLima()}`).then(v => { setVig(v); setValores({}) }).catch(() => setVig(null))
  }
  useEffect(() => { if (emp) cargar(emp) }, [emp])

  const efectivas = vig?.efectivas ?? {}
  const propuesta = useMemo(() => aplicar(efectivas, valores), [efectivas, valores])
  const cuerpo = () => ({ empresa_id: emp, valid_from: validFrom, motivo, config: propuesta })

  const enviar = async (ruta: string) => {
    setMsg(''); const loc = validarLocal(validFrom, motivo, hoyLima()); setErrores(loc)
    if (Object.keys(loc).length) return null
    try { return await api(ruta, { method: 'POST', body: cuerpo() }) } catch (e: any) {
      setErrores(erroresPorCampo(e.detail)); setMsg(e.message); return null
    }
  }
  const previsualizar = async () => { const r = await enviar('/rule-sets/preview'); if (r) { setCambios(r.diff); setContra(r.contra_version) } }
  const publicar = async () => {
    if (!cambios) return setMsg('Previsualiza los cambios antes de publicar')
    if (!await confirmar({ titulo: 'Publicar versión', mensaje: `¿Publicar nueva versión vigente desde ${validFrom}? Las versiones son inmutables.`, ok: 'Publicar' })) return
    const r = await enviar('/rule-sets'); if (r && emp) { cargar(emp); setValidFrom(''); setMotivo(''); ok(`Versión ${r.version} publicada`) }
  }
  const err = (k: string) => errores[k] && <small className="error text-xs font-normal text-danger" data-campo={k}>{errores[k]}</small>

  const TH = 'border-b border-border px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted'
  const TD = 'border-b border-border px-3 py-2'
  return <div className="grid gap-5">
    <Card><label className="flex max-w-md flex-col gap-1 text-xs font-medium text-muted">Empresa <select className="ds-input" aria-label="Empresa" value={emp ?? ''} onChange={e => setEmp(Number(e.target.value))}>
      {emps.map(e => <option key={e.id} value={e.id}>{e.razon_social}</option>)}</select></label></Card>
    <Card className="!p-0 overflow-hidden"><h3 className="m-0 px-5 pt-4 pb-2 text-base">Historial de versiones</h3>
    <div className="overflow-x-auto"><table className="w-full border-collapse text-sm"><thead><tr><th className={TH}>Versión</th><th className={TH}>Vigente desde</th><th className={TH}>Motivo</th><th className={TH}>Creado</th></tr></thead>
      <tbody>{hist.map(h => { const v = vig?.rule_set_id === h.id
        return <tr key={h.id} className={v ? 'act bg-accent-soft/50' : ''}><td className={TD}><b>v{h.version}</b>{v && <> <Pill tono="success">(vigente)</Pill></>}</td>
        <td className={TD}>{h.valid_from}</td><td className={TD}>{h.motivo ?? '—'}</td><td className={TD}>{h.creado_en?.slice(0, 16).replace('T', ' ') ?? ''}</td></tr> })}</tbody></table></div></Card>

    <Card><h3 className="m-0 mb-4 text-base">{admin ? 'Nueva versión' : 'Valores vigentes'}</h3>
    <form onSubmit={e => e.preventDefault()} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {CAMPOS_REGLA.map(c => {
        const v = c.ruta in valores ? valores[c.ruta] : leer(efectivas, c.ruta)
        const set = (crudo: string | boolean) => { setCambios(null); setValores(o => ({ ...o, [c.ruta]: convertir(c, crudo) })) }
        return <label key={c.ruta} title={c.ayuda} className={cn('flex gap-1 text-xs font-medium text-muted', c.tipo === 'bool' ? 'flex-row-reverse items-center justify-end' : 'flex-col')}>{c.label}
          {Array.isArray(c.tipo) ? <select className="ds-input" disabled={!admin} value={String(v ?? '')} onChange={e => set(e.target.value)}>{c.tipo.map(o => <option key={o}>{o}</option>)}</select>
            : c.tipo === 'bool' ? <input type="checkbox" className="size-4 accent-[var(--c-accent)]" disabled={!admin} checked={Boolean(v)} onChange={e => set(e.target.checked)} />
              : <input className="ds-input" type={c.tipo === 'time' ? 'time' : 'number'} step={c.tipo === 'number' ? 'any' : undefined} disabled={!admin} value={v == null ? '' : String(v)} onChange={e => set(e.target.value)} />}
          {err(c.ruta)}</label>
      })}
      {admin && <>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">Vigente desde <input className="ds-input" type="date" aria-label="Vigente desde" value={validFrom} onChange={e => { setValidFrom(e.target.value); setCambios(null) }} />{err('valid_from')}</label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">Motivo <input className="ds-input" aria-label="Motivo" value={motivo} onChange={e => setMotivo(e.target.value)} />{err('motivo')}</label>
        <div className="flex flex-wrap items-end gap-2 sm:col-span-2 xl:col-span-3"><Button icon={Eye} onClick={previsualizar}>Previsualizar cambios</Button>
          <Button variant="primary" icon={Send} onClick={publicar} disabled={!cambios}>Publicar versión</Button></div>
      </>}
    </form></Card>
    {msg && <div className="error rounded-ctl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert"><p className="m-0">{msg}</p>
      {erroresGenerales(errores).length > 0 && <ul className="m-0 mt-1">{erroresGenerales(errores).map(e => <li key={e}>{e}</li>)}</ul>}</div>}
    {cambios && <Card className="!p-0 overflow-hidden"><h3 className="m-0 px-5 pt-4 pb-2 text-base">Cambios contra v{contra ?? '—'}</h3>
      {cambios.length === 0 ? <p className="m-0 px-5 pb-4 text-sm text-muted">Sin cambios respecto a la versión vigente.</p> :
        <table className="w-full border-collapse text-sm"><thead><tr><th className={TH}>Regla</th><th className={TH}>Antes</th><th className={TH}>Después</th></tr></thead>
          <tbody>{cambios.map(c => <tr key={c.ruta}><td className={cn(TD, 'font-mono text-xs')}>{c.ruta}</td><td className={cn(TD, 'text-danger')}>{fmt(c.antes)}</td><td className={cn(TD, 'text-success font-semibold')}>{fmt(c.despues)}</td></tr>)}</tbody></table>}</Card>}
  </div>
}
