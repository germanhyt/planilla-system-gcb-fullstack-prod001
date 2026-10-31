import { useEffect, useState } from 'react'
import { api } from './api'

/** Solo admin: empresa de cada usuario (vacio = global). Cambio auditado; el jefe queda en la empresa de su unidad. */
export function Usuarios() {
  const [users, setUsers] = useState<any[]>([]); const [emps, setEmps] = useState<any[]>([])
  const [sel, setSel] = useState<Record<number, string>>({}); const [msg, setMsg] = useState('')
  const cargar = () => api('/usuarios').then(setUsers).catch(e => setMsg(e.message))
  useEffect(() => { cargar(); api('/empresas').then(setEmps).catch(() => {}) }, [])
  const guardar = async (u: any) => {
    setMsg('')
    const v = sel[u.id] ?? (u.empresa_id ? String(u.empresa_id) : '')
    try {
      await api(`/usuarios/${u.id}/empresa`, { method: 'PUT', body: { empresa_id: v ? Number(v) : null } })
      setMsg(`Empresa de ${u.email} actualizada`); cargar()
    } catch (e: any) { setMsg(e.message) }
  }
  return <div><h2>Usuarios</h2>{msg && <p role="status">{msg}</p>}
    <table><thead><tr><th>Email</th><th>Rol</th><th>Unidad</th><th>Empresa</th><th></th></tr></thead><tbody>
      {users.map(u => <tr key={u.id}><td>{u.email}</td><td>{u.rol}</td><td>{u.unidad_id ?? ''}</td>
        <td><select aria-label={`Empresa de ${u.email}`} value={sel[u.id] ?? (u.empresa_id ? String(u.empresa_id) : '')}
          onChange={e => setSel({ ...sel, [u.id]: e.target.value })}>
          <option value="">(global)</option>{emps.map(e => <option key={e.id} value={e.id}>{e.razon_social}</option>)}</select></td>
        <td><button onClick={() => guardar(u)}>Guardar</button></td></tr>)}
    </tbody></table></div>
}
