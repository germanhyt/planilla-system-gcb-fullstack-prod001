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
import { vistaInicial } from './shell/menuLib'
import { Dashboard } from './Dashboard'
import { useForm } from 'react-hook-form'
import { yupResolver } from '@hookform/resolvers/yup'
import * as yup from 'yup'
import { Save, Scale, User as UserIcon } from 'lucide-react'
import { Button, Card, ErrorBox, Field, PageHeader, Pantalla } from './ui'
import { fallo, ok } from './ui/feedback'
import { hoyLima } from './ui/hooks'
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

const esquemaLogin = yup.object({ email: yup.string().trim().required('Ingrese su correo').email('Correo no válido'), password: yup.string().required('Ingrese su contraseña') })

function Login({ onOk }: { onOk: () => void }) {
  const [err, setErr] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: yupResolver(esquemaLogin), defaultValues: { email: '', password: '' } })
  const entrar = async (v: { email: string; password: string }) => {
    setErr('')
    try { const r = await api('/auth/login', { method: 'POST', body: v }); localStorage.setItem('token', r.access_token); reintentarTrasLogin(); onOk() }
    catch (e: any) { setErr(e.message) }
  }
  return <div className="ds login-wrap"><form className="login" onSubmit={handleSubmit(entrar)} noValidate>
    <div className="login-brand"><img src="/brand/logo-mark-dark-bg.png" alt="GCB" /><span>Planillas</span></div>
    <div><h1>Planillas GCB</h1><p className="m-0 text-sm text-muted">Control de asistencia y horas para planilla.</p></div>
    <label className="grid gap-1 text-sm font-medium text-fg">Correo<input className="ds-input" placeholder="Correo" type="email" autoComplete="username" aria-invalid={!!errors.email} {...register('email')} />
      {errors.email && <small className="text-xs text-danger">{errors.email.message}</small>}</label>
    <label className="grid gap-1 text-sm font-medium text-fg">Contraseña<input className="ds-input" placeholder="Contraseña" type="password" autoComplete="current-password" aria-invalid={!!errors.password} {...register('password')} />
      {errors.password && <small className="text-xs text-danger">{errors.password.message}</small>}</label>
    <Button variant="primary" type="submit" disabled={isSubmitting} className="h-11 w-full justify-center">{isSubmitting ? 'Ingresando…' : 'Ingresar'}</Button>
    {err && <p className="err m-0 text-sm" role="alert">{err}</p>}</form></div>
}

const esquemaPerfil = yup.object({ nombre: yup.string().trim().required('Requerido').max(120), telefono: yup.string().trim().max(30).default('') })

function Perfil({ me, recargar }: { me: any; recargar: () => void }) {
  const [ficha, setFicha] = useState<any>(null)
  useEffect(() => { api('/me/trabajador').then(setFicha).catch(() => {}) }, [])
  const { register, handleSubmit, formState: { errors, isSubmitting, isDirty }, reset } = useForm({ resolver: yupResolver(esquemaPerfil), defaultValues: { nombre: me.nombre ?? '', telefono: me.telefono || '' } })
  const guardar = async (v: any) => { try { await api('/me', { method: 'PUT', body: v }); ok('Guardado'); reset(v); recargar() } catch (e) { fallo(e) } }
  const ini = (me.nombre || '?').split(' ').map((x: string) => x[0]).slice(0, 2).join('').toUpperCase()
  return <Pantalla>
    <section className="grid gap-4"><PageHeader titulo="Mi perfil" icon={UserIcon} desc="Datos de contacto de su cuenta." />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="flex flex-col items-center gap-2 text-center"><span className="grid size-16 place-items-center rounded-full bg-primary text-xl font-bold text-primary-fg">{ini}</span>
          <p className="m-0 font-semibold">{me.nombre}</p><p className="m-0 text-sm text-muted">{me.email} — rol <b className="capitalize">{me.rol}</b></p>
          {ficha && <p className="m-0 text-sm text-muted">Mi ficha: {ficha.codigo} · {ficha.area} · {ficha.cargo}</p>}</Card>
        <Card className="lg:col-span-2"><form onSubmit={handleSubmit(guardar)} noValidate className="grid gap-4 sm:grid-cols-2">
          <Field label="Nombre" error={errors.nombre?.message as string | undefined}><input className="ds-input" {...register('nombre')} /></Field>
          <Field label="Teléfono" error={errors.telefono?.message as string | undefined}><input className="ds-input" {...register('telefono')} /></Field>
          <div className="sm:col-span-2"><Button variant="primary" type="submit" icon={Save} disabled={isSubmitting || !isDirty}>Guardar</Button></div></form></Card>
      </div></section>
  </Pantalla>
}

function Reglas() {
  const [emps, setEmps] = useState<any[]>([]); const [sel, setSel] = useState<any>(null); const [emp, setEmp] = useState<number | null>(null)
  const [fecha, setFecha] = useState(hoyLima())
  useEffect(() => { api('/empresas').then(setEmps).catch(fallo) }, [])
  const ver = (id: number) => { setEmp(id); api(`/rule-sets/vigente?empresa_id=${id}&fecha=${fecha}`).then(setSel).catch(x => setSel({ error: x.message })) }
  return <Pantalla><section className="grid gap-4">
    <PageHeader titulo="Reglas vigentes (rule_set)" icon={Scale} desc="Consulte el rule_set vigente de cada empresa a una fecha." />
    <Card className="flex flex-wrap items-end gap-3">
      <Field label="Fecha"><input className="ds-input" type="date" value={fecha} onChange={e => setFecha(e.target.value)} /></Field>
      {emps.map(e => <Button key={e.id} variant={emp === e.id ? 'primary' : 'secondary'} onClick={() => ver(e.id)}>{e.razon_social}</Button>)}
    </Card>
    {sel && (sel.error ? <ErrorBox msg={sel.error} /> : <Card><pre className="m-0 max-h-[60vh] overflow-auto rounded-ctl bg-surface-2 p-3 text-xs">{JSON.stringify(sel, null, 2)}</pre></Card>)}
  </section></Pantalla>
}

function App() {
  const [me, setMe] = useState<any>(null); const [vista, setVista] = useState('')
  const cargar = () => getToken() && api('/me').then(setMe).catch(() => setMe(null))
  useEffect(() => { cargar() }, [])
  const [tick, setTick] = useState(0)
  const noLeidas = useConteoNotificaciones(!!me && (me.rol === 'rrhh' || me.rol === 'admin'), tick)
  if (!getToken() || !me) return <Login onOk={cargar} />
  const r = me.rol; const v = vista || vistaInicial(r); const admin = r === 'admin'; const rrhh = r === 'rrhh' || admin
  return <Shell me={me} vista={v} setVista={setVista} noLeidas={noLeidas} onNotif={() => setTick(x => x + 1)}>
      {v === 'dashboard' && <Dashboard rol={r} />}
      {v === 'perfil' && <Perfil me={me} recargar={cargar} />}
      {v === 'marcar' && <Marcador token={getToken()!} />}
      {v === 'mis-marcas' && <MisMarcas />}
      {v === 'marcas' && <MarcasEquipo rol={r} />}
      {v === 'horarios' && <Horarios rol={r} />}
      {v === 'he' && <HEProgramadas rol={r} />}
      {v === 'justificaciones' && <Justificaciones rol={r} />}
      {v === 'excepciones' && <Excepciones rol={r} />}
      {v === 'bolsa' && <BolsaHoras rol={r} />}
      {v === 'reportes' && <Reportes rol={r} />}
      {v === 'bonos' && <Bonos rol={r} meId={me.id} />}
      {v === 'periodos' && <Periodos rol={r} />}
      {v === 'notificaciones' && <Notificaciones onCambio={() => setTick(x => x + 1)} />}
      {v === 'empresas' && <Crud titulo="Empresas" ruta="/empresas" campos={EMPRESA} puedeEscribir={admin} />}
      {v === 'unidades' && <Crud titulo="Unidades" ruta="/unidades" campos={UNIDAD} puedeEscribir={admin} />}
      {v === 'sedes' && <Crud titulo="Sedes" ruta="/sedes" campos={SEDE} puedeEscribir={admin} />}
      {v === 'contratos' && <Crud titulo="Tipos de contrato" ruta="/tipos-contrato" campos={CONTRATO} puedeEscribir={admin} />}
      {v === 'trabajadores' && <Crud titulo="Trabajadores" ruta="/trabajadores" campos={TRAB} puedeEscribir={rrhh} />}
      {v === 'reglas' && <Reglas />}
      {v === 'usuarios' && <Usuarios />}
      {v === 'configuracion' && <Configuracion admin={admin} contrato={CONTRATO} />}
  </Shell>
}

// Estilos base en @layer base (las utilidades de Tailwind siempre ganan). Sin reglas genéricas de button/input: todas las vistas usan el DS.
const css = `@layer base{
body{margin:0;font-family:var(--font);background:var(--c-bg);color:var(--c-text);-webkit-font-smoothing:antialiased}
[data-theme="light"] .logo-dark,:root:not([data-theme="light"]) .logo-light{display:none}
.app-main{font-size:14px;line-height:1.5}.app-main h2{font-size:20px;font-weight:600;margin:0;letter-spacing:-.01em}.app-main h3{font-size:15px;font-weight:600}
.app-main a{color:var(--c-accent)}.app-main pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.ds-input{display:block;width:100%;min-height:36px;background:var(--c-surface);color:var(--c-text);border:1px solid var(--c-border);border-radius:var(--r-md);padding:7px 10px;font:inherit;font-size:14px;transition:border-color .15s,box-shadow .15s}
.ds-input:hover{border-color:color-mix(in srgb,var(--c-accent) 40%,var(--c-border))}
.ds-input:focus{outline:none;border-color:var(--c-accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--c-accent) 25%,transparent)}
.ds-input[aria-invalid="true"]{border-color:var(--c-danger)}.ds-input:disabled{opacity:.6;cursor:not-allowed}
select.ds-input{padding-right:28px}
.ds-pg{display:inline-grid;place-items:center;min-width:30px;height:30px;padding:0 8px;border:1px solid var(--c-border);border-radius:8px;background:var(--c-surface);color:var(--c-text);font:inherit;font-size:12px;cursor:pointer}
.ds-pg:hover:not(:disabled){border-color:var(--c-accent);color:var(--c-accent)}.ds-pg:disabled{opacity:.4;cursor:not-allowed}
.ds-dt td,.ds-dt th{border-bottom:1px solid var(--c-border)}.ds-dt tbody tr:last-child td{border-bottom:0}
.ds-progress{appearance:none;-webkit-appearance:none;height:8px;border:0;border-radius:999px;background:var(--c-surface-2);overflow:hidden}.ds-progress::-webkit-progress-bar{background:var(--c-surface-2)}.ds-progress::-webkit-progress-value{background:var(--c-accent);border-radius:999px}.ds-progress::-moz-progress-bar{background:var(--c-accent)}
.ds-scroll{scrollbar-width:thin;scrollbar-color:color-mix(in srgb,var(--c-muted) 45%,transparent) transparent}
.ds-scroll::-webkit-scrollbar{width:8px;height:8px}.ds-scroll::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--c-muted) 45%,transparent);border-radius:8px;border:2px solid transparent;background-clip:padding-box}
.ds-scroll::-webkit-scrollbar-track{background:transparent}
.ds-scroll-dark{scrollbar-color:rgba(255,255,255,.22) transparent}.ds-scroll-dark::-webkit-scrollbar-thumb{background:rgba(255,255,255,.22);background-clip:padding-box}
.Toastify__toast-container{position:fixed;z-index:9999}
.ds-toast{background:var(--c-surface)!important;color:var(--c-text)!important;border:1px solid var(--c-border);border-radius:var(--r-lg)!important;box-shadow:0 12px 32px rgba(0,0,0,.25)!important;font-family:var(--font)!important;font-size:14px}
.ds-toast .Toastify__close-button{color:var(--c-muted)}
.login-wrap{min-height:100vh;display:grid;place-items:center;padding:16px;background:radial-gradient(1200px 600px at 10% -10%,color-mix(in srgb,var(--c-accent) 22%,transparent),transparent),var(--c-bg)}
.login{width:100%;max-width:380px;display:flex;flex-direction:column;gap:14px;background:var(--c-surface);border:1px solid var(--c-border);border-radius:16px;padding:32px;box-shadow:0 24px 60px rgba(0,0,0,.25)}
.login-brand{display:flex;align-items:center;gap:10px;align-self:flex-start;background:linear-gradient(180deg,var(--c-sidebar-2),var(--c-sidebar));color:#fff;border-radius:12px;padding:8px 12px;font-weight:600}
.login-brand img{height:28px}.login h1{font-size:22px;margin:0 0 2px;letter-spacing:-.01em}
.err{color:var(--c-danger)}.alerta{color:var(--c-warning);background:var(--c-warning-bg);padding:2px 6px;font-size:12px;margin-top:2px;border-radius:6px}tr.sel{background:var(--c-surface-2)}
}`
document.head.insertAdjacentHTML('beforeend', `<style>${css}</style>`)
document.head.insertAdjacentHTML('beforeend', `<style id="gcb-tokens">${buildThemeCss()}</style>`)
applyTheme(getTheme(typeof localStorage === 'undefined' ? null : localStorage), document)
// /design-preview solo en DEV (import.meta.env.DEV es false en build -> el chunk se elimina)
const DesignPreview = import.meta.env.DEV ? lazy(() => import('./design/DesignPreview')) : null
createRoot(document.getElementById('root')!).render(
  DesignPreview && location.pathname === '/design-preview' ? <Suspense fallback={null}><DesignPreview /></Suspense> : <App />)
