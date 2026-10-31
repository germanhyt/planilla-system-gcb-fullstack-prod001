import { useEffect, useState } from 'react'
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
import { textoBadge } from './trabajosLib'
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
  return <form className="login" onSubmit={entrar}><h1>Planillas GCB</h1>
    <input placeholder="Correo" value={email} onChange={e => setEmail(e.target.value)} />
    <input placeholder="Contraseña" type="password" value={password} onChange={e => setPassword(e.target.value)} />
    <button>Ingresar</button>{err && <p className="err">{err}</p>}</form>
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
  const r = me.rol; const admin = r === 'admin'; const rrhh = r === 'rrhh' || admin; const jefe = r === 'jefe' || rrhh
  const trabajador = r === 'trabajador' || jefe
  const menu: [string, string, boolean][] = [['perfil', 'Mi perfil', true], ['marcar', 'Marcar asistencia', trabajador], ['mis-marcas', 'Mis marcas', r === 'trabajador'], ['marcas', 'Marcas', jefe], ['horarios', 'Horarios', jefe], ['he', 'Horas extra programadas', trabajador], ['justificaciones', r === 'trabajador' ? 'Justificar falta' : 'Justificaciones', trabajador], ['excepciones', 'Excepciones', jefe], ['reportes', 'Reportes', jefe], ['bonos', 'Bono 3 AM', rrhh], ['periodos', 'Cierre de periodo', rrhh], ['notificaciones', 'Notificaciones', rrhh], ['bolsa', r === 'trabajador' ? 'Mi bolsa de horas' : 'Bolsa de horas', true], ['empresas', 'Empresas', jefe], ['unidades', 'Unidades', jefe], ['sedes', 'Sedes', jefe],
    ['contratos', 'Tipos de contrato', jefe], ['trabajadores', 'Trabajadores', jefe], ['reglas', 'Reglas', jefe && !rrhh], ['usuarios', 'Usuarios', admin], ['configuracion', 'Configuración', rrhh]]
  return <div><nav>{menu.filter(m => m[2]).map(([k, l]) => <button key={k} className={vista === k ? 'act' : ''} onClick={() => setVista(k)}>{l}{k === 'notificaciones' && noLeidas > 0 && <b data-testid="badge-notif" className="badge">{textoBadge(noLeidas)}</b>}</button>)}
    <span>{me.nombre} ({r})</span><button onClick={() => { localStorage.removeItem('token'); location.reload() }}>Salir</button></nav>
    <main>
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
    </main></div>
}

const css = `body{font-family:system-ui;margin:0}nav{background:#1e3a5f;padding:8px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}nav span{color:#fff;margin-left:auto}
nav .act{font-weight:bold}main{padding:12px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #ccc;padding:4px}
.form{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;background:#f4f6fa;padding:10px;margin-bottom:10px}label{display:flex;flex-direction:column;font-size:13px}
.login{max-width:320px;margin:80px auto;display:flex;flex-direction:column;gap:8px}.err{color:#b00}
.alerta{color:#8a5a00;background:#fff4dc;padding:2px 6px;font-size:12px;margin-top:2px}.decision{display:flex;flex-wrap:wrap;gap:4px;align-items:center}tr.sel{background:#eef4ff}.badge{background:#c62828;color:#fff;border-radius:9px;padding:0 6px;margin-left:4px;font-size:11px}`
document.head.insertAdjacentHTML('beforeend', `<style>${css}</style>`)
createRoot(document.getElementById('root')!).render(<App />)
