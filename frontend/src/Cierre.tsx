import { useEffect, useState } from 'react'
import { api } from './api'
import { ProgresoTrabajo, useTrabajo } from './Trabajos'

const mesActual = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' }).slice(0, 7)
const soles = (v: any) => v === null || v === undefined || v === '' ? '—' : `S/ ${Number(v).toFixed(2)}`

function useEmpresas() {
  const [emps, setEmps] = useState<any[]>([])
  useEffect(() => { api('/empresas').then(setEmps).catch(() => {}) }, [])
  return emps
}

/** Bono nocturno 3 AM (interno, no es el recargo legal): admin registra monto; otra persona RRHH/admin aprueba. */
export function Bonos({ rol, meId }: { rol: string; meId: number }) {
  const emps = useEmpresas()
  const [empresa, setEmpresa] = useState(''); const [periodo, setPeriodo] = useState(mesActual())
  const [lista, setLista] = useState<any[]>([]); const [trabs, setTrabs] = useState<any[]>([])
  const [f, setF] = useState({ trabajador_id: '', cantidad: '1', monto: '', observacion: '' })
  const [hist, setHist] = useState<any[] | null>(null); const [msg, setMsg] = useState('')
  const admin = rol === 'admin'
  const cargar = () => {
    const q = new URLSearchParams({ periodo, ...(empresa ? { empresa_id: empresa } : {}) })
    api(`/bonos-nocturnos?${q}`).then(setLista).catch(e => setMsg(e.message))
  }
  useEffect(() => { cargar() }, [empresa, periodo])
  useEffect(() => { api('/trabajadores').then(setTrabs).catch(() => {}) }, [])
  const guardar = async () => {
    setMsg('')
    try {
      await api('/bonos-nocturnos', { method: 'POST', body: { trabajador_id: Number(f.trabajador_id), periodo, cantidad: Number(f.cantidad),
        monto: f.monto === '' ? null : f.monto, observacion: f.observacion || null } })
      setMsg('Bono registrado: queda pendiente de aprobación por otra persona.'); setF({ ...f, monto: '', observacion: '' }); cargar()
    } catch (e: any) { setMsg(e.message) }
  }
  const decidir = async (b: any, aprobar: boolean) => {
    const comentario = prompt(aprobar ? 'Comentario (opcional)' : 'Motivo del rechazo') ?? undefined
    if (!aprobar && !comentario) return
    try { await api(`/bonos-nocturnos/${b.id}/decision`, { method: 'POST', body: { aprobar, comentario } }); cargar() }
    catch (e: any) { setMsg(e.message) }
  }
  const trabsVis = trabs.filter(t => !empresa || String(t.empresa_id) === empresa)
  return <section><h2>Bono nocturno 3 AM</h2>
    <p className="nota">Ingreso interno (no es el recargo nocturno legal). Admin registra cantidad y monto por trabajador y periodo; lo aprueba otra persona (RRHH/admin). Todo queda auditado. Periodo cerrado = no editable.</p>
    <label>Empresa <select value={empresa} onChange={e => setEmpresa(e.target.value)}><option value="">Todas</option>
      {emps.map(e => <option key={e.id} value={e.id}>{e.codigo}</option>)}</select></label>
    <label>Periodo <input type="month" value={periodo} onChange={e => setPeriodo(e.target.value)} /></label>
    {admin && <div className="form-inline"><h3>Registrar / corregir</h3>
      <select value={f.trabajador_id} onChange={e => setF({ ...f, trabajador_id: e.target.value })}><option value="">Trabajador…</option>
        {trabsVis.map(t => <option key={t.id} value={t.id}>{t.codigo} - {t.nombres} {t.apellidos}</option>)}</select>
      <input type="number" min="0" placeholder="Cantidad" value={f.cantidad} onChange={e => setF({ ...f, cantidad: e.target.value })} />
      <input type="number" min="0" step="0.01" placeholder="Monto S/" value={f.monto} onChange={e => setF({ ...f, monto: e.target.value })} />
      <input placeholder="Observación" value={f.observacion} onChange={e => setF({ ...f, observacion: e.target.value })} />
      <button disabled={!f.trabajador_id} onClick={guardar}>Guardar</button></div>}
    {msg && <p className="err">{msg}</p>}
    <table><thead><tr><th>Trabajador</th><th>Periodo</th><th>Cantidad</th><th>Monto</th><th>Estado</th><th>Registró</th><th>Aprobó</th><th></th></tr></thead>
      <tbody>{lista.map(b => <tr key={b.id}><td>{b.trabajador_codigo} {b.trabajador}</td><td>{b.periodo}{b.periodo_cerrado ? ' 🔒' : ''}</td>
        <td>{b.cantidad}</td><td>{soles(b.monto)}</td><td>{b.estado}</td><td>{b.registrado_por_email}</td><td>{b.aprobado_por_email || ''}</td>
        <td>{b.estado === 'registrado' && !b.periodo_cerrado && b.registrado_por !== meId && <>
          <button onClick={() => decidir(b, true)}>Aprobar</button><button onClick={() => decidir(b, false)}>Rechazar</button></>}
          <button onClick={() => api(`/bonos-nocturnos/${b.id}/historial`).then(setHist)}>Historial</button></td></tr>)}</tbody></table>
    {hist && <div><h3>Historial <button onClick={() => setHist(null)}>×</button></h3><ul>{hist.map((h, i) =>
      <li key={i}>{new Date(h.ts).toLocaleString('es-PE', { timeZone: 'America/Lima' })} — {h.accion} — cant. {h.cantidad} — {soles(h.monto)} — {h.estado}{h.comentario ? ` — ${h.comentario}` : ''}</li>)}</ul></div>}
  </section>
}

const ETIQUETAS: Record<string, string> = { he_sin_decidir: 'HE sin decidir', excepciones_pendientes: 'Excepciones pendientes (fuera de geocerca)',
  marcas_incompletas: 'Marcas impares/incompletas', bonos_sin_aprobar: 'Bonos 3 AM sin aprobar' }

/** Cierre de periodo (mes calendario por día operativo): checklist, confirmación, cierre y reapertura (sólo admin). */
export function Periodos({ rol }: { rol: string }) {
  const emps = useEmpresas()
  const [empresa, setEmpresa] = useState(''); const [periodo, setPeriodo] = useState(mesActual())
  const [ck, setCk] = useState<any>(null); const [hist, setHist] = useState<any[]>([]); const [msg, setMsg] = useState('')
  const [confirmando, setConfirmando] = useState(false);
  const { trabajo, seguir, limpiar } = useTrabajo()
  useEffect(() => { if (!empresa && emps.length) setEmpresa(String(emps[0].id)) }, [emps])
  const cargar = () => {
    if (!empresa) return
    setMsg(''); setConfirmando(false)
    api(`/periodos/checklist?empresa_id=${empresa}&periodo=${periodo}`).then(setCk).catch(e => setMsg(e.message))
    api(`/periodos/historial?empresa_id=${empresa}`).then(setHist).catch(() => {})
  }
  useEffect(() => { cargar() }, [empresa, periodo])
  const cerrar = async () => {
    try {
      await api('/periodos/cerrar', { method: 'POST', body: { empresa_id: Number(empresa), periodo, confirmar: true } })
      setMsg(`Periodo ${periodo} cerrado.`); cargar()
    } catch (e: any) { setMsg(e.message) }
  }
  const reabrir = async (c: any) => {
    const razon = prompt('Motivo de la reapertura (mínimo 10 caracteres)')
    if (!razon) return
    try { await api(`/periodos/reabrir/${c.id}`, { method: 'POST', body: { razon_reapertura: razon } }); setMsg(`Periodo ${c.periodo} reabierto.`); cargar() }
    catch (e: any) { setMsg(e.message) }
  }
  const recalcular = async () => {
    setMsg(''); limpiar()
    try {
      const r = await api(`/periodos/recalcular?empresa_id=${empresa}&periodo=${periodo}`, { method: 'POST' })
      if (r.trabajo) { const fin = await seguir(r.trabajo); setMsg(fin.estado === 'ok' ? `Recalculo de ${periodo} completado.` : `Recalculo con error: ${fin.error}`) }
      else setMsg(`Recalculados ${r.trabajadores_recalculados} trabajador(es).`)
      cargar()
    } catch (e: any) { setMsg(e.message) }
  }
  const pend = ck?.total_pendientes ?? 0
  return <section><h2>Cierre de periodo</h2>
    <p className="nota">Periodo = mes calendario por día operativo. Cerrado: se bloquean marcas, regularizaciones y bonos (409). Exportación FINAL a Planilla Core sólo con periodo cerrado. Reabrir: sólo admin, con motivo (auditado).</p>
    <label>Empresa <select value={empresa} onChange={e => setEmpresa(e.target.value)}>{emps.map(e => <option key={e.id} value={e.id}>{e.codigo}</option>)}</select></label>
    <label>Periodo <input type="month" value={periodo} onChange={e => setPeriodo(e.target.value)} /></label>
    <button onClick={cargar}>Actualizar</button>
    {!ck?.cerrado && <button onClick={recalcular}>Recalcular periodo</button>}
    <ProgresoTrabajo t={trabajo} />
    {msg && <p className="err">{msg}</p>}
    {ck && <div><h3>Checklist {ck.periodo} ({ck.desde} a {ck.hasta}) — {ck.cerrado ? '🔒 CERRADO' : 'abierto'}</h3>
      <ul>{Object.entries(ck.conteos).map(([k, v]: any) => <li key={k} className={v ? 'warn' : ''}>{v ? '⚠️' : '✅'} {ETIQUETAS[k] || k}: <b>{v}</b>
        {v > 0 && <details><summary>ver</summary><pre>{JSON.stringify(ck[k], null, 1)}</pre></details>}</li>)}</ul>
      {!ck.cerrado && !confirmando && <button onClick={() => setConfirmando(true)}>Cerrar periodo…</button>}
      {!ck.cerrado && confirmando && <div className="confirm">
        {pend > 0 ? <p className="err">Hay {pend} pendiente(s). Si cierra igual, quedarán congelados tal como están.</p> : <p>Sin pendientes.</p>}
        <p>¿Confirma el cierre de {ck.periodo}? Después no se podrán modificar marcas, regularizaciones ni bonos.</p>
        <button onClick={cerrar}>Sí, cerrar {pend > 0 ? 'con pendientes' : ''}</button><button onClick={() => setConfirmando(false)}>Cancelar</button></div>}
    </div>}
    <h3>Historial de cierres</h3>
    <table><thead><tr><th>Periodo</th><th>Estado</th><th>Cerrado</th><th>Reapertura</th><th></th></tr></thead>
      <tbody>{hist.map(c => <tr key={c.id}><td>{c.periodo}</td><td>{c.estado}</td><td>{c.cerrado_en ? new Date(c.cerrado_en).toLocaleString('es-PE', { timeZone: 'America/Lima' }) : ''}</td>
        <td>{c.razon_reapertura || ''}</td><td>{rol === 'admin' && c.estado === 'cerrado' && <button onClick={() => reabrir(c)}>Reabrir</button>}</td></tr>)}</tbody></table>
  </section>
}
