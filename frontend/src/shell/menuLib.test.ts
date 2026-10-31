import { describe, expect, it } from 'vitest'
import { construirMenu, migas, puedeFiltrarEmpresa, vistaInicial } from './menuLib'
const ks = (r: string) => construirMenu(r).flatMap(g => g.items.map(i => i.k))
describe('menú del shell por rol', () => {
  it('trabajador: simple, sin config ni cumplimiento', () => {
    expect(ks('trabajador')).toEqual(['perfil', 'marcar', 'mis-marcas', 'bolsa', 'he', 'justificaciones'])
    expect(construirMenu('trabajador').map(g => g.titulo)).toEqual(['Principal', 'Asistencia'])
  })
  it('jefe ve reglas pero no cierre, notificaciones ni configuración', () => {
    const k = ks('jefe'); expect(k).toContain('reglas'); expect(k).not.toContain('periodos'); expect(k).not.toContain('notificaciones'); expect(k).not.toContain('configuracion')
  })
  it('rrhh sin usuarios ni reglas; admin con todo menos reglas', () => {
    expect(ks('rrhh')).not.toContain('usuarios'); expect(ks('rrhh')).not.toContain('reglas')
    expect(ks('admin')).toHaveLength(20); expect(construirMenu('admin').map(g => g.titulo)).toEqual(['Principal', 'Asistencia', 'Reportes', 'Cumplimiento', 'Configuración'])
  })
  it('dashboard para jefe/rrhh/admin y vista inicial por rol', () => {
    expect(ks('trabajador')).not.toContain('dashboard')
    for (const r of ['jefe', 'rrhh', 'admin']) { expect(ks(r)[0]).toBe('dashboard'); expect(vistaInicial(r)).toBe('dashboard') }
    expect(vistaInicial('trabajador')).toBe('marcar')
  })
  it('migas y filtro de empresa', () => {
    expect(migas(construirMenu('admin'), 'periodos')).toEqual(['Cumplimiento', 'Cierre de periodo'])
    expect(migas(construirMenu('jefe'), 'dashboard')).toEqual(['Principal', 'Dashboard'])
    expect(puedeFiltrarEmpresa('rrhh')).toBe(true); expect(puedeFiltrarEmpresa('jefe')).toBe(false)
  })
})
