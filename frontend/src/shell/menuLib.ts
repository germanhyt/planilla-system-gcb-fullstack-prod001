// Menú del shell agrupado por secciones y filtrado por rol (misma visibilidad que el menú plano anterior).
export type Rol = 'trabajador' | 'jefe' | 'rrhh' | 'admin' | string
export type ItemMenu = { k: string; label: string; icon: string }
export type GrupoMenu = { titulo: string; items: ItemMenu[] }

export function construirMenu(r: Rol): GrupoMenu[] {
  const admin = r === 'admin', rrhh = r === 'rrhh' || admin, jefe = r === 'jefe' || rrhh, trabajador = r === 'trabajador' || jefe
  const T = r === 'trabajador'
  const g = (titulo: string, items: [string, string, string, boolean][]): GrupoMenu =>
    ({ titulo, items: items.filter(i => i[3]).map(([k, label, icon]) => ({ k, label, icon })) })
  return [
    g('Principal', [['perfil', 'Mi perfil', 'user', true], ['marcar', 'Marcar asistencia', 'fingerprint', trabajador],
      ['mis-marcas', 'Mis marcas', 'list', T], ['notificaciones', 'Notificaciones', 'bell', rrhh],
      ['bolsa', T ? 'Mi bolsa de horas' : 'Bolsa de horas', 'piggy', true]]),
    g('Asistencia', [['marcas', 'Marcas', 'clock', jefe], ['horarios', 'Horarios', 'calendar', jefe],
      ['he', 'Horas extra programadas', 'timer', trabajador], ['justificaciones', T ? 'Justificar falta' : 'Justificaciones', 'file', trabajador],
      ['excepciones', 'Excepciones', 'alert', jefe]]),
    g('Reportes', [['reportes', 'Reportes', 'chart', jefe]]),
    g('Cumplimiento', [['bonos', 'Bono 3 AM', 'moon', rrhh], ['periodos', 'Cierre de periodo', 'lock', rrhh], ['reglas', 'Reglas', 'scale', jefe && !rrhh]]),
    g('Configuración', [['empresas', 'Empresas', 'building', jefe], ['unidades', 'Unidades', 'boxes', jefe], ['sedes', 'Sedes', 'map', jefe],
      ['contratos', 'Tipos de contrato', 'contract', jefe], ['trabajadores', 'Trabajadores', 'users', jefe],
      ['usuarios', 'Usuarios', 'shield', admin], ['configuracion', 'Configuración', 'settings', rrhh]]),
  ].filter(x => x.items.length > 0)
}

export function migas(grupos: GrupoMenu[], vista: string): [string, string] {
  for (const g of grupos) for (const i of g.items) if (i.k === vista) return [g.titulo, i.label]
  return ['Principal', 'Mi perfil']
}
export const puedeFiltrarEmpresa = (r: Rol) => r === 'admin' || r === 'rrhh'
