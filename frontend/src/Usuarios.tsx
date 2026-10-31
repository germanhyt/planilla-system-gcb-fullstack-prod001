import { useEffect, useMemo, useState } from 'react'
import { Save, UserCog } from 'lucide-react'
import { api } from './api'
import { Button, PageHeader, Pantalla, Pill } from './ui'
import { Chips, DataTable, type ColumnDef } from './ui/DataTable'
import { fallo, ok } from './ui/feedback'
import { useEmpresaFiltro } from './ui/empresaFiltro'

const TONO_ROL: Record<string, 'accent' | 'warning' | 'success' | 'neutral'> = { admin: 'accent', rrhh: 'success', jefe: 'warning', trabajador: 'neutral' }

/** Solo admin: empresa de cada usuario (vacio = global). Cambio auditado; el jefe queda en la empresa de su unidad. */
export function Usuarios() {
  const empresa = useEmpresaFiltro()
  const [emps, setEmps] = useState<any[]>([]); const [sel, setSel] = useState<Record<number, string>>({}); const [rol, setRol] = useState('')
  const [recarga, setRecarga] = useState(0)
  useEffect(() => { api('/empresas').then(setEmps).catch(() => {}) }, [])
  const guardar = async (u: any) => {
    const v = sel[u.id] ?? (u.empresa_id ? String(u.empresa_id) : '')
    try { await api(`/usuarios/${u.id}/empresa`, { method: 'PUT', body: { empresa_id: v ? Number(v) : null } }); ok(`Empresa de ${u.email} actualizada`); setRecarga(n => n + 1) }
    catch (e) { fallo(e) }
  }
  const cols = useMemo<ColumnDef<any, any>[]>(() => [
    { accessorKey: 'email', header: 'Email', cell: x => <span className="flex items-center gap-2"><span className="grid size-8 place-items-center rounded-full bg-accent-soft text-xs font-bold uppercase text-accent">{String(x.getValue()).slice(0, 2)}</span>{x.getValue()}</span> },
    { accessorKey: 'rol', header: 'Rol', cell: x => <Pill tono={TONO_ROL[x.getValue()] ?? 'neutral'} className="capitalize">{x.getValue()}</Pill> },
    { accessorKey: 'unidad_id', header: 'Unidad', cell: x => x.getValue() ?? '' },
    { id: 'emp', header: 'Empresa', enableSorting: false, cell: x => { const u = x.row.original
      return <select className="ds-input h-8 !py-0" aria-label={`Empresa de ${u.email}`} value={sel[u.id] ?? (u.empresa_id ? String(u.empresa_id) : '')} onChange={e => setSel(s => ({ ...s, [u.id]: e.target.value }))}>
        <option value="">(global)</option>{emps.map(e => <option key={e.id} value={e.id}>{e.razon_social}</option>)}</select> } },
    { id: 'acc', header: '', enableSorting: false, cell: x => <Button size="sm" variant="primary" icon={Save} onClick={() => guardar(x.row.original)}>Guardar</Button> },
  ], [emps, sel])
  return <Pantalla>
    <PageHeader titulo="Usuarios" icon={UserCog} desc="Empresa de cada usuario (vacío = global). El cambio queda auditado; el jefe queda en la empresa de su unidad." />
    <DataTable data={[]} columns={cols} servidor={{ url: '/usuarios', clave: 'usuarios', recarga, params: { rol, empresa_id: empresa } }} buscar="Buscar email" tam={20}
      chips={<Chips label="Rol" valor={rol} onChange={setRol} chips={[{ valor: '', label: 'Todos' }, { valor: 'admin', label: 'Admin' }, { valor: 'rrhh', label: 'RRHH' }, { valor: 'jefe', label: 'Jefe' }, { valor: 'trabajador', label: 'Trabajador' }]} />} />
  </Pantalla>
}
