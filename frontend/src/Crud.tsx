import { useEffect, useState } from 'react'
import { api } from './api'

export type Campo = { k: string; label: string; tipo?: 'text' | 'number' | 'date' | 'time' | 'checkbox' | 'select'; opciones?: string; req?: boolean }
type Props = { titulo: string; ruta: string; campos: Campo[]; puedeEscribir: boolean }

export function Crud({ titulo, ruta, campos, puedeEscribir }: Props) {
  const [filas, setFilas] = useState<any[]>([])
  const [form, setForm] = useState<any | null>(null)
  const [ops, setOps] = useState<Record<string, any[]>>({})
  const [err, setErr] = useState('')
  const cargar = () => api(ruta).then(setFilas).catch(e => setErr(e.message))
  useEffect(() => {
    cargar()
    campos.filter(c => c.opciones).forEach(c => api(c.opciones!).then(d => setOps(o => ({ ...o, [c.k]: d }))).catch(() => {}))
  }, [ruta])
  const etiqueta = (c: Campo, v: any) => {
    const o = ops[c.k]?.find(x => x.id === v)
    return o ? (o.codigo || o.nombre || o.razon_social || o.id) : String(v ?? '')
  }
  const guardar = async () => {
    setErr('')
    const body: any = {}
    for (const c of campos) {
      let v = form[c.k]
      if (v === '' || v === undefined) v = null
      if (v !== null && (c.tipo === 'number' || c.tipo === 'select')) v = Number(v)
      body[c.k] = c.tipo === 'checkbox' ? !!v : v
    }
    if ('activo' in (form || {})) body.activo = form.activo
    try {
      await api(form.id ? `${ruta}/${form.id}` : ruta, { method: form.id ? 'PUT' : 'POST', body })
      setForm(null); cargar()
    } catch (e: any) { setErr(e.message) }
  }
  const borrar = async (id: number) => { if (confirm('¿Desactivar registro?')) { await api(`${ruta}/${id}`, { method: 'DELETE' }); cargar() } }
  return (
    <section>
      <h2>{titulo} {puedeEscribir && <button onClick={() => setForm({})}>+ Nuevo</button>}</h2>
      {err && <p className="err">{err}</p>}
      {form && (
        <div className="form">
          {campos.map(c => (
            <label key={c.k}>{c.label}{c.req && ' *'}
              {c.tipo === 'select' ? (
                <select value={form[c.k] ?? ''} onChange={e => setForm({ ...form, [c.k]: e.target.value })}>
                  <option value="">—</option>
                  {(ops[c.k] || []).map(o => <option key={o.id} value={o.id}>{o.codigo || o.nombre || o.razon_social || o.email}</option>)}
                </select>
              ) : c.tipo === 'checkbox' ? (
                <input type="checkbox" checked={!!form[c.k]} onChange={e => setForm({ ...form, [c.k]: e.target.checked })} />
              ) : (
                <input type={c.tipo || 'text'} value={form[c.k] ?? ''} onChange={e => setForm({ ...form, [c.k]: e.target.value })} />
              )}
            </label>
          ))}
          <div><button onClick={guardar}>Guardar</button> <button onClick={() => setForm(null)}>Cancelar</button></div>
        </div>
      )}
      <table>
        <thead><tr>{campos.slice(0, 7).map(c => <th key={c.k}>{c.label}</th>)}<th /></tr></thead>
        <tbody>{filas.map(f => (
          <tr key={f.id}>{campos.slice(0, 7).map(c => <td key={c.k}>{c.tipo === 'select' ? etiqueta(c, f[c.k]) : c.tipo === 'checkbox' ? (f[c.k] ? 'Sí' : 'No') : String(f[c.k] ?? '')}</td>)}
            <td>{puedeEscribir && <><button onClick={() => setForm(f)}>Editar</button> <button onClick={() => borrar(f.id)}>Desactivar</button></>}</td></tr>
        ))}</tbody>
      </table>
    </section>
  )
}
