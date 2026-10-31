import { lazy, Suspense, useEffect, useState } from 'react'
import './theme/theme.css'
import { buildThemeCss } from './theme/tokens'
import { applyTheme, getTheme } from './theme/theme'
import { createRoot } from 'react-dom/client'
import { api, getToken } from './api'
import { Crud, Campo } from './Crud'
import { Marcador } from './Marcador'
import { MarcasEquipo, MisMarcas } from './Marcas'
import { BolsaHoras, Excepciones } from './Excepciones'
import { Reportes } from './Reportes'
import { Bonos, Periodos } from './Cierre'
import { HEProgramadas } from './Programacion'
import { Horarios } from './Horarios'
import { Justificaciones } from './Justificaciones'
import { Configuracion } from './Configuracion'
import { Usuarios } from './Usuarios'
import { Notificaciones, useConteoNotificaciones } from './Trabajos'
import { Shell } from './shell/Shell'
import { EVENTO_SESION_EXPIRADA, reintentarTrasLogin } from './offlineQueue'

// Token vencido al sincronizar marcas offline: volver al login sin perder la cola (IndexedDB persiste).
window.addEventListener(EVENTO_SESION_EXPIRADA, () => { if (getToken()) { localStorage.removeItem('token'); location.reload() } })

const EMPRESA: Campo[] = [{ k: 'codigo', label: 'Código', req: true }, { k: 'razon_social', label: 'Razón social', req: true }, { k: 'ruc', label: 'RUC', req: true }]
const UNIDAD: Campo[] = [{ k: 'empresa_id', label: 'Empresa', tipo: 'select', opciones: '/empresas', req: true }, { k: 'codigo', label: 'Código', req: true }, { k: 'nombre', label: 'Nombre', req: true }]
const SEDE: Campo[] = [{ k: 'unidad_id', label: 'Unidad', tipo: 'select', opciones: '/unidades', req: true }, { k: 'nombre', label: 'Nombre', req: true },
  { k: 'lat', label: 'Latitud', tipo: 'number', req: true }, { k: 'lng', label: 'Longitud', tipo: 'number', req: true }, { k: 'radio_geocerca_m', label: 'Radio geocerca (m)', tipo: 'number' }, { k: 'direccion', label: 'Dirección' }]
const CONTRATO: Campo[] = [{ k: 'codigo', label: 'Código', req: true }, { k: 'nombre', label: 'Nombre', req: true }, { k: 'horas_mes', label: 'Horas/mes', tipo: 'number', req: true },
  { k: 'jornada_diaria_min', label: 'Jornada diaria (min)', tipo: 'number', req: true }, { k: 'es_part_time', label: 'Part time', tipo: 'checkbox' }, { k: 'refrigerio_min', label: 'Refrigerio (min)', tipo: 'number' }]
const TRAB: Campo[] = [{ k: 'codigo', label: 'Código', req: true }, { k: 'nombres', label: 'Nombres', req: true }, { k: 'apellidos', label: 'Apellidos', req: true },
  { k: 'unidad_id', label: 'Unidad', tipo: 'select', opciones: '/unidades', req: true }, { k: 'area', label: 'Área' }, { k: 'cargo', label: 'Cargo' },
  { k: 'tipo_contrato_id', label: 'Contrato', tipo: 'select', opciones: '/tipos-contrato', req: true },
  { k: 'empresa_id', label: 'Empresa', tipo: 'select', opciones: '/empresas', req: true }, { k: 'sede_id', label: 'Sede', tipo: 'select', opciones: '/sedes' },
  { k: 'doc_tipo', label: 'Tipo doc.', req: true }, { k: 'doc_numero', label: 'N° doc.', req: true }, { k: 'jornada_diaria_min', label: 'Jornada diaria (min, override)', tipo: 'number' },
  { k: 'fecha_ingreso', label: 'Fecha ingreso', tipo: 'date', req: true }, { k: 'fecha_cese', label: 'Fecha cese', tipo: 'date' }]

function Login({ onOk }: { onOk: () => void }) {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [err, setErr] = useState('')
  const entrar = async (e: React.FormEvent) => {
    e.preventDefault()
    try { const r = await api('/auth/login', { method: 'POST', body: { email, password } }); localStorage.setItem('token', r.access_token); reintentarTrasLogin(); onOk() }
    catch (e: any) { setErr(e.message) }
  }
  return <div className="ds login-wrap"><form className="login" onSubmit={entrar}><img src="/brand/logo-mark-dark-bg.png" alt="GCB" className="logo-dark" /><img src="/brand/logo-mark-light-bg.png" alt="GCB" className="logo-light" /><h1>Planillas GCB</h1>
    <input placeholder="Correo" value={email} onChange={e => setEmail(e.target.value)} />
    <input placeholder="Contraseña" type="password" value={password} onChange={e => setPassword(e.target.value)} />
    <button>Ingresar</button>{err && <p className="err">{err}</p>}</form></div>
}

function Perfil({ me, recargar }: { me: any; recargar: () => void }) {
  const [f, setF] = useState({ nombre: me.nombre, telefono: me.telefono || '' }); const [msg, setMsg] = useState('')
  const [ficha, setFicha] = useState<any>(null)
  useEffect(() => { api('/me/trabajador').then(setFicha).catch(() => {}) }, [])
  return <section><h2>Mi perfil</h2><p>{me.email} — rol <b>{me.rol}</b></p>
    <label>Nombre <input value={f.nombre} onChange={e => setF({ ...f, nombre: e.target.value })} /></label>
    <label>Teléfono <input value={f.telefono} onChange={e => setF({ ...f, telefono: e.target.value })} /></label>
    <button onClick={async () => { await api('/me', { method: 'PUT', body: f }); setMsg('Guardado'); recargar() }}>Guardar</button> {msg}
    {ficha && <p>Mi ficha: {ficha.codigo} · {ficha.area} · {ficha.cargo}</p>}</section>
}

function Reglas() {
  const [emps, setEmps] = useState<any[]>([]); const [sel, setSel] = useState<any>(null)
  const [fecha, setFecha] = useState(new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' }))
  useEffect(() => { api('/empresas').then(setEmps) }, [])
  return <section><h2>Reglas vigentes (rule_set)</h2>
    <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} />
    {emps.map(e => <button key={e.id} onClick={() => api(`/rule-sets/vigente?empresa_id=${e.id}&fecha=${fecha}`).then(setSel).catch(x => setSel({ error: x.message }))}>{e.razon_social}</button>)}
    {sel && <pre>{JSON.stringify(sel, null, 2)}</pre>}</section>
}

function App() {
  const [me, setMe] = useState<any>(null); const [vista, setVista] = useState('perfil')
  const cargar = () => getToken() && api('/me').then(setMe).catch(() => setMe(null))
  useEffect(() => { cargar() }, [])
  const [tick, setTick] = useState(0)
  const noLeidas = useConteoNotificaciones(!!me && (me.rol === 'rrhh' || me.rol === 'admin'), tick)
  if (!getToken() || !me) return <Login onOk={cargar} />
  const r = me.rol; const admin = r === 'admin'; const rrhh = r === 'rrhh' || admin
  return <Shell me={me} vista={vista} setVista={setVista} noLeidas={noLeidas}>
      {vista === 'perfil' && <Perfil me={me} recargar={cargar} />}
      {vista === 'marcar' && <Marcador token={getToken()!} />}
      {vista === 'mis-marcas' && <MisMarcas />}
      {vista === 'marcas' && <MarcasEquipo rol={r} />}
      {vista === 'horarios' && <Horarios rol={r} />}
      {vista === 'he' && <HEProgramadas rol={r} />}
      {vista === 'justificaciones' && <Justificaciones rol={r} />}
      {vista === 'excepciones' && <Excepciones rol={r} />}
      {vista === 'bolsa' && <BolsaHoras rol={r} />}
      {vista === 'reportes' && <Reportes rol={r} />}
      {vista === 'bonos' && <Bonos rol={r} meId={me.id} />}
      {vista === 'periodos' && <Periodos rol={r} />}
      {vista === 'notificaciones' && <Notificaciones onCambio={() => setTick(x => x + 1)} />}
      {vista === 'empresas' && <Crud titulo="Empresas" ruta="/empresas" campos={EMPRESA} puedeEscribir={admin} />}
      {vista === 'unidades' && <Crud titulo="Unidades" ruta="/unidades" campos={UNIDAD} puedeEscribir={admin} />}
      {vista === 'sedes' && <Crud titulo="Sedes" ruta="/sedes" campos={SEDE} puedeEscribir={admin} />}
      {vista === 'contratos' && <Crud titulo="Tipos de contrato" ruta="/tipos-contrato" campos={CONTRATO} puedeEscribir={admin} />}
      {vista === 'trabajadores' && <Crud titulo="Trabajadores" ruta="/trabajadores" campos={TRAB} puedeEscribir={rrhh} />}
      {vista === 'reglas' && <Reglas />}
      {vista === 'usuarios' && <Usuarios />}
      {vista === 'configuracion' && <Configuracion admin={admin} contrato={CONTRATO} />}
  </Shell>
}

const css = `body{margin:0;font-family:var(--font);background:var(--c-bg);color:var(--c-text);-webkit-font-smoothing:antialiased}
[data-theme="light"] .logo-dark,:root:not([data-theme="light"]) .logo-light{display:none}
.app-main{font-size:14px;line-height:1.5}.app-main h2{font-size:20px;font-weight:600;margin:0 0 12px;letter-spacing:-.01em}.app-main h3{font-size:15px;font-weight:600}
.app-main>section,.app-main>div{background:var(--c-surface);border:1px solid var(--c-border);border-radius:var(--r-lg);padding:16px 20px;overflow-x:auto}
.app-main input,.app-main select,.app-main textarea,.login input{background:var(--c-surface);color:var(--c-text);border:1px solid var(--c-border);border-radius:8px;padding:6px 8px;font:inherit}
.app-main button,.login button{background:var(--c-surface-2);color:var(--c-text);border:1px solid var(--c-border);border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer;margin:2px}
.app-main button:hover{border-color:var(--c-muted)}.app-main button:disabled{opacity:.5;cursor:not-allowed}
.app-main a{color:var(--c-blue)}.app-main pre{background:var(--c-surface-2);padding:10px;border-radius:8px;overflow:auto}
section nav{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}section nav .act{font-weight:bold;border-color:var(--c-text)}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--c-border);padding:8px;text-align:left}th{background:var(--c-surface-2);color:var(--c-muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.form{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;background:var(--c-surface-2);border:1px solid var(--c-border);border-radius:var(--r-md);padding:12px;margin-bottom:10px}label{display:flex;flex-direction:column;font-size:13px;color:var(--c-muted);gap:2px}
.login-wrap{min-height:100vh;display:grid;place-items:center;padding:16px}.login{width:100%;max-width:340px;display:flex;flex-direction:column;gap:10px;background:var(--c-surface);border:1px solid var(--c-border);border-radius:var(--r-lg);padding:28px}
.login img{height:36px;align-self:flex-start}.login h1{font-size:20px;margin:4px 0 8px}.login input{padding:10px 12px}.login button{background:var(--c-primary);color:var(--c-primary-fg);border:0;padding:10px;font-weight:600;margin:0}
.err{color:var(--c-danger)}.alerta{color:var(--c-warning);background:var(--c-warning-bg);padding:2px 6px;font-size:12px;margin-top:2px;border-radius:6px}.decision{display:flex;flex-wrap:wrap;gap:4px;align-items:center}tr.sel{background:var(--c-surface-2)}
.badge{background:var(--c-danger);color:var(--c-surface);border-radius:9px;padding:0 6px;margin-left:4px;font-size:11px}`
document.head.insertAdjacentHTML('beforeend', `<style>${css}</style>`)
document.head.insertAdjacentHTML('beforeend', `<style id="gcb-tokens">${buildThemeCss()}</style>`)
applyTheme(getTheme(typeof localStorage === 'undefined' ? null : localStorage), document)
// /design-preview solo en DEV (import.meta.env.DEV es false en build -> el chunk se elimina)
const DesignPreview = import.meta.env.DEV ? lazy(() => import('./design/DesignPreview')) : null
createRoot(document.getElementById('root')!).render(
  DesignPreview && location.pathname === '/design-preview' ? <Suspense fallback={null}><DesignPreview /></Suspense> : <App />)
