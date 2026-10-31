/** Sprint 3 / Incremento 3: Reportes mensuales (RRHH/admin todo, jefe sólo su unidad) y exportación a Planilla Core. */
import { useEffect, useState } from 'react'
import { api, getToken } from './api'
import { ProgresoTrabajo, useTrabajo, VersionesExport } from './Trabajos'

const mesActual = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Lima' }).slice(0, 7)
const n = (v: number | null | undefined) => (v === null || v === undefined ? '—' : Number(v).toFixed(2))

interface Fila {
  trabajador_id: number; codigo: string; trabajador: string; empresa: string; horas_trabajadas: number; horas_normales: number
  tardanza_min: number; horas_extra_25: number; horas_extra_35: number; horas_nocturnas: number; recargo_nocturno_horas: number | null
  bono_3am: number; bono_3am_monto: number; banco_horas_mes: number; banco_horas_saldo: number; ausencias: number
}
interface Resp { periodo: string; desde: string; hasta: string; periodo_cerrado?: boolean; muestra_recargo_nocturno?: boolean; registros: Fila[]; totales: Record<string, number> }

async function descargar(path: string, method = 'GET'): Promise<{ nombre: string; estado: string | null; reutilizada: boolean }> {
  const r = await fetch('/api' + path, { method, headers: { Authorization: `Bearer ${getToken()}` } })
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(typeof d.detail === 'string' ? d.detail : String(r.status)) }
  const nombre = /filename=([^;]+)/.exec(r.headers.get('content-disposition') || '')?.[1] || 'reporte'
  const url = URL.createObjectURL(await r.blob()); const a = document.createElement('a'); a.href = url; a.download = nombre; a.click(); URL.revokeObjectURL(url)
  return { nombre, estado: r.headers.get('x-export-estado'), reutilizada: r.headers.get('x-export-reutilizada') === 'true' }
}

export function Reportes({ rol }: { rol: string }) {
  const gestor = rol === 'rrhh' || rol === 'admin'
  const [empresas, setEmpresas] = useState<any[]>([]); const [empresa, setEmpresa] = useState(''); const [periodo, setPeriodo] = useState(mesActual())
  const { trabajo, seguir, limpiar } = useTrabajo(); const [recarga, setRecarga] = useState(0)
  const [data, setData] = useState<Resp | null>(null); const [err, setErr] = useState(''); const [msg, setMsg] = useState(''); const [fmtPc, setFmtPc] = useState<'csv' | 'json'>('csv')
  useEffect(() => { api<any[]>('/empresas').then(e => { setEmpresas(e); if (e.length && !empresa) setEmpresa(String(e[0].id)) }).catch(() => {}) }, [])
  const q = () => { const p = new URLSearchParams({ periodo }); if (empresa) p.set('empresa_id', empresa); return p }
  const cargar = () => { setErr(''); setMsg(''); api<Resp>(`/reportes/consolidado-mensual?${q()}`).then(setData).catch(e => setErr(e.message)) }
  useEffect(() => { if (periodo) cargar() }, [empresa, periodo])
  const recargo = data?.muestra_recargo_nocturno ?? data?.registros.some(r => r.recargo_nocturno_horas !== null)
  const bajar = (formato: string) => descargar(`/reportes/consolidado-mensual?${q()}&formato=${formato}`).catch(e => setErr(e.message))
  const exportar = async () => {
    if (!empresa) { setErr('Seleccione una empresa'); return }
    if (data && !data.periodo_cerrado && !confirm('El periodo no está cerrado: el archivo se generará marcado PRELIMINAR. ¿Continuar?')) return
    setErr(''); try { const r = await descargar(`/reportes/export-planilla-core?${q()}&formato=${fmtPc}`, 'POST'); setRecarga(x => x + 1); setMsg(r.reutilizada ? `Sin cambios: se reutiliza ${r.nombre} (checksum igual).` : `Generado ${r.nombre} (${r.estado}). Registrado en auditoría.`) } catch (e: any) { setErr(e.message) }
  }
  const exportarLote = async () => {
    setErr(''); setMsg(''); limpiar()
    try {
      const p = new URLSearchParams({ periodo, formato: fmtPc }); if (empresa) p.set('empresa_id', empresa)
      const tr = await api(`/reportes/export-planilla-core/lote?${p}`, { method: 'POST' })
      const fin = await seguir(tr); setRecarga(x => x + 1)
      if (fin.estado === 'ok') setMsg(`Lote exportado (${fin.total} empresa(s)). Ver versiones abajo.`); else setErr(fin.error || 'Error en lote')
    } catch (e: any) { setErr(e.message) }
  }
  const t = data?.totales
  return <section><h2>Reportes {rol === 'jefe' ? 'de mi unidad' : ''}</h2>
    <p style={{ fontSize: 13, color: '#555' }}>Mes calendario; cada turno cuenta en el mes de su día operativo. Horas nocturnas 22:00–06:00 siempre calculadas;
      el recargo nocturno se muestra aparte sólo en empresas que lo pagan por separado (según sus reglas: nocturno.mostrar_sobretasa_separada). Bono 3 AM: cantidad aprobada (monto lo fija administración).</p>
    <div className="form">
      <label>Empresa <select value={empresa} onChange={e => setEmpresa(e.target.value)}>
        {gestor && <option value="">Todas</option>}{empresas.map(e => <option key={e.id} value={e.id}>{e.codigo}</option>)}</select></label>
      <label>Periodo <input type="month" value={periodo} onChange={e => setPeriodo(e.target.value)} /></label>
      <button onClick={cargar}>Actualizar</button>
      <button onClick={() => bajar('csv')}>⬇ CSV</button>
      <button onClick={() => bajar('xlsx')}>⬇ XLSX</button>
      {gestor && <><select value={fmtPc} onChange={e => setFmtPc(e.target.value as 'csv' | 'json')} title="Formato interfaz"><option value="csv">CSV</option><option value="json">JSON</option></select>
        <button onClick={exportar} disabled={!empresa}>Exportar a Planilla Core</button>
        <button onClick={exportarLote}>Exportar lote (segundo plano)</button></>}
    </div>
    {data && empresa && <p>Periodo {data.desde} a {data.hasta}: <b style={{ color: data.periodo_cerrado ? '#1b7f3b' : '#b26a00' }}>{data.periodo_cerrado ? 'CERRADO (export FINAL)' : 'ABIERTO (export PRELIMINAR)'}</b></p>}
    <ProgresoTrabajo t={trabajo} />
    {err && <p className="err">{err}</p>}{msg && <p style={{ color: '#1b7f3b' }}>{msg}</p>}
    {data && (data.registros.length === 0 ? <p>Sin asistencia registrada en el periodo.</p> :
      <div style={{ overflowX: 'auto' }}><table><thead><tr><th>Código</th><th>Trabajador</th><th>Empresa</th><th>H. trabajadas</th><th>H. normales</th><th>Tardanza (min)</th>
        <th>HE 25%</th><th>HE 35%</th><th>H. nocturnas 22-06</th>{recargo && <th>Recargo nocturno (h)</th>}<th>Bono 3 AM</th><th>Bono 3 AM (S/)</th><th>Banco h. (mes)</th><th>Banco h. (saldo)</th><th>Ausencias</th></tr></thead>
        <tbody>{data.registros.map(r => <tr key={r.trabajador_id}><td>{r.codigo}</td><td>{r.trabajador}</td><td>{r.empresa}</td><td>{n(r.horas_trabajadas)}</td><td>{n(r.horas_normales)}</td>
          <td>{r.tardanza_min}</td><td>{n(r.horas_extra_25)}</td><td>{n(r.horas_extra_35)}</td><td>{n(r.horas_nocturnas)}</td>{recargo && <td>{n(r.recargo_nocturno_horas)}</td>}
          <td>{r.bono_3am}</td><td>{r.bono_3am_monto ? r.bono_3am_monto.toFixed(2) : ''}</td><td>{n(r.banco_horas_mes)}</td><td>{n(r.banco_horas_saldo)}</td><td>{r.ausencias}</td></tr>)}</tbody>
        {t && <tfoot><tr><th colSpan={3}>Total ({t.total_trabajadores})</th><th>{n(t.total_horas_trabajadas)}</th><th>{n(t.total_horas_normales)}</th><th>{t.total_tardanza_min}</th>
          <th>{n(t.total_horas_extra_25)}</th><th>{n(t.total_horas_extra_35)}</th><th>{n(t.total_horas_nocturnas)}</th>{recargo && <th>{n(t.total_recargo_nocturno_horas)}</th>}
          <th>{t.total_bono_3am}</th><th>{Number(t.total_bono_3am_monto || 0).toFixed(2)}</th><th>{n(t.total_banco_horas_mes)}</th><th>{n(t.total_banco_horas_saldo)}</th><th></th></tr></tfoot>}
      </table></div>)}
    {gestor && <VersionesExport empresa={empresa} periodo={periodo} recarga={recarga} />}
  </section>
}
