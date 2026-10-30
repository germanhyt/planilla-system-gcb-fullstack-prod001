import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { Crud, Campo } from './Crud'
import { aplicar, CAMPOS_REGLA, Cambio, convertir, erroresPorCampo, leer, validarLocal } from './configLib'

const hoyLima = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
const fmt = (v: unknown) => (v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))

export function Configuracion({ admin, contrato }: { admin: boolean; contrato: Campo[] }) {
  const [tab, setTab] = useState<'reglas' | 'contratos'>('reglas')
  return <section><h2>Configuración</h2>
    {!admin && <p className="aviso">Solo lectura: los cambios de configuración los publica un administrador.</p>}
    <nav><button className={tab === 'reglas' ? 'act' : ''} onClick={() => setTab('reglas')}>Reglas por empresa</button>
      <button className={tab === 'contratos' ? 'act' : ''} onClick={() => setTab('contratos')}>Tipos de contrato</button></nav>
    {tab === 'reglas' ? <ReglasEmpresa admin={admin} /> : <Crud titulo="Tipos de contrato" ruta="/tipos-contrato" campos={contrato} puedeEscribir={admin} />}
  </section>
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
    if (!confirm(`¿Publicar nueva versión vigente desde ${validFrom}? Las versiones son inmutables.`)) return
    const r = await enviar('/rule-sets'); if (r && emp) { cargar(emp); setValidFrom(''); setMotivo(''); setMsg(`Versión ${r.version} publicada`) }
  }
  const err = (k: string) => errores[k] && <small className="error" data-campo={k}>{errores[k]}</small>

  return <div>
    <label>Empresa <select aria-label="Empresa" value={emp ?? ''} onChange={e => setEmp(Number(e.target.value))}>
      {emps.map(e => <option key={e.id} value={e.id}>{e.razon_social}</option>)}</select></label>
    <h3>Historial de versiones</h3>
    <table><thead><tr><th>Versión</th><th>Vigente desde</th><th>Motivo</th><th>Creado</th></tr></thead>
      <tbody>{hist.map(h => <tr key={h.id} className={vig?.rule_set_id === h.id ? 'act' : ''}><td>v{h.version}{vig?.rule_set_id === h.id ? ' (vigente)' : ''}</td>
        <td>{h.valid_from}</td><td>{h.motivo ?? '—'}</td><td>{h.creado_en?.slice(0, 16).replace('T', ' ') ?? ''}</td></tr>)}</tbody></table>

    <h3>{admin ? 'Nueva versión' : 'Valores vigentes'}</h3>
    <form onSubmit={e => e.preventDefault()} className="grid">
      {CAMPOS_REGLA.map(c => {
        const v = c.ruta in valores ? valores[c.ruta] : leer(efectivas, c.ruta)
        const set = (crudo: string | boolean) => { setCambios(null); setValores(o => ({ ...o, [c.ruta]: convertir(c, crudo) })) }
        return <label key={c.ruta} title={c.ayuda}>{c.label}
          {Array.isArray(c.tipo) ? <select disabled={!admin} value={String(v ?? '')} onChange={e => set(e.target.value)}>{c.tipo.map(o => <option key={o}>{o}</option>)}</select>
            : c.tipo === 'bool' ? <input type="checkbox" disabled={!admin} checked={Boolean(v)} onChange={e => set(e.target.checked)} />
              : <input type={c.tipo === 'time' ? 'time' : 'number'} disabled={!admin} value={v == null ? '' : String(v)} onChange={e => set(e.target.value)} />}
          {err(c.ruta)}</label>
      })}
      {admin && <>
        <label>Vigente desde <input type="date" aria-label="Vigente desde" value={validFrom} onChange={e => { setValidFrom(e.target.value); setCambios(null) }} />{err('valid_from')}</label>
        <label>Motivo <input aria-label="Motivo" value={motivo} onChange={e => setMotivo(e.target.value)} />{err('motivo')}</label>
        <div><button type="button" onClick={previsualizar}>Previsualizar cambios</button>
          <button type="button" onClick={publicar} disabled={!cambios}>Publicar versión</button></div>
      </>}
    </form>
    {msg && <p className="error" role="alert">{msg}</p>}
    {cambios && <div><h3>Cambios contra v{contra ?? '—'}</h3>
      {cambios.length === 0 ? <p>Sin cambios respecto a la versión vigente.</p> :
        <table><thead><tr><th>Regla</th><th>Antes</th><th>Después</th></tr></thead>
          <tbody>{cambios.map(c => <tr key={c.ruta}><td>{c.ruta}</td><td>{fmt(c.antes)}</td><td>{fmt(c.despues)}</td></tr>)}</tbody></table>}</div>}
  </div>
}
