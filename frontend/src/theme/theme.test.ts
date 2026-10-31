import { describe, expect, it } from 'vitest'
import { DEFAULT_THEME, THEME_KEY, applyTheme, getTheme, setTheme, toggleTheme } from './theme'
import { buildThemeCss, contrast, tokens } from './tokens'

function mem() { const m = new Map<string, string>(); return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), m } }
function fakeDoc() {
  const attrs: Record<string, string> = {}, meta: Record<string, string> = {}
  return { attrs, meta, documentElement: { setAttribute: (n: string, v: string) => { attrs[n] = v } },
    querySelector: () => ({ setAttribute: (n: string, v: string) => { meta[n] = v } }) }
}

describe('theme toggle', () => {
  it('default es dark (sin storage, vacío o valor inválido)', () => {
    expect(DEFAULT_THEME).toBe('dark')
    expect(getTheme(null)).toBe('dark')
    const s = mem(); expect(getTheme(s)).toBe('dark')
    s.setItem(THEME_KEY, 'azul'); expect(getTheme(s)).toBe('dark')
  })
  it('toggle alterna, persiste en localStorage y aplica data-theme + meta theme-color', () => {
    const s = mem(), d = fakeDoc()
    expect(toggleTheme(s, d)).toBe('light')
    expect(s.m.get(THEME_KEY)).toBe('light')
    expect(d.attrs['data-theme']).toBe('light')
    expect(d.meta.content).toBe(tokens.light.bg)
    expect(getTheme(s)).toBe('light')
    expect(toggleTheme(s, d)).toBe('dark')
    expect(d.attrs['data-theme']).toBe('dark')
  })
  it('tolera storage que lanza (modo privado)', () => {
    const bad = { getItem: () => { throw new Error('x') }, setItem: () => { throw new Error('x') } }
    expect(getTheme(bad)).toBe('dark')
    expect(setTheme('light', bad, null)).toBe('light')
    expect(() => applyTheme('dark', null)).not.toThrow()
  })
  it('CSS: dark en :root y override light', () => {
    const css = buildThemeCss()
    expect(css).toContain(`:root,[data-theme="dark"]{--c-bg:${tokens.dark.bg}`)
    expect(css).toContain(`[data-theme="light"]{--c-bg:${tokens.light.bg}`)
  })
  it('acento morado reemplaza al azul en ambos temas', () => {
    for (const t of ['dark', 'light'] as const) {
      expect(tokens[t]).not.toHaveProperty('blue')
      const n = parseInt(tokens[t].accent.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255
      expect(b).toBeGreaterThan(g); expect(r).toBeGreaterThan(g)
    }
  })
  it.each(['dark', 'light'] as const)('contraste accesible WCAG AA en %s', t => {
    const k = tokens[t]
    expect(contrast(k.text, k.bg)).toBeGreaterThanOrEqual(7)
    expect(contrast(k.muted, k.surface)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(k['primary-fg'], k.primary)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(k.accent, k.surface)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(k.text, k['accent-soft'])).toBeGreaterThanOrEqual(4.5)
    // sidebar berenjena: texto blanco y secundario legibles, item activo morado claro con texto blanco
    expect(contrast(k['sidebar-fg'], k.sidebar)).toBeGreaterThanOrEqual(7)
    expect(contrast(k['sidebar-fg'], k['sidebar-2'])).toBeGreaterThanOrEqual(7)
    expect(contrast(k['sidebar-muted'], k.sidebar)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(k['sidebar-fg'], k['sidebar-active'])).toBeGreaterThanOrEqual(4.5)
    for (const s of ['success', 'warning', 'danger'] as const) expect(contrast(k[s], k[`${s}-bg`])).toBeGreaterThanOrEqual(4.5)
    for (const s of ['success', 'danger'] as const) expect(contrast(k[s], k.surface)).toBeGreaterThanOrEqual(4.5)
  })
})
