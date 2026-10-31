// Design tokens (fuente única). Estilo "Nex HR dashboard": sidebar berenjena, acento morado profundo; estados ámbar/verde/rojo.
export type Theme = 'dark' | 'light'
export type Tokens = Record<string, string>

export const tokens: Record<Theme, Tokens> = {
  dark: {
    bg: '#0e0a14', surface: '#160f20', 'surface-2': '#1e1529', border: '#2e2240',
    text: '#efeaf6', muted: '#a89bbd',
    primary: '#7c3aed', 'primary-fg': '#ffffff',
    'pill-active': '#2a1b3d',
    accent: '#a78bfa', 'accent-strong': '#8b5cf6', 'accent-soft': '#2a1b3d', amber: '#fbbf24', teal: '#2dd4bf',
    sidebar: '#1e0a2e', 'sidebar-2': '#2a0a3d', 'sidebar-fg': '#ffffff', 'sidebar-muted': '#c4b2d9', 'sidebar-active': '#4a1d6e',
    success: '#4ade80', 'success-bg': '#0f2e22',
    warning: '#fbbf24', 'warning-bg': '#33270b',
    danger: '#f87171', 'danger-bg': '#3a1515',
  },
  light: {
    bg: '#f6f4f9', surface: '#ffffff', 'surface-2': '#f3eff8', border: '#e6e0ee',
    text: '#1a1025', muted: '#5f5470',
    primary: '#2d0b45', 'primary-fg': '#ffffff',
    'pill-active': '#ede5f7',
    accent: '#6d28d9', 'accent-strong': '#6d28d9', 'accent-soft': '#ede5f7', amber: '#b45309', teal: '#0f766e',
    sidebar: '#2a0a3d', 'sidebar-2': '#1e0a2e', 'sidebar-fg': '#ffffff', 'sidebar-muted': '#cbbbe0', 'sidebar-active': '#5b2a86',
    success: '#047857', 'success-bg': '#d1fae5',
    warning: '#92400e', 'warning-bg': '#fef3c7',
    danger: '#b91c1c', 'danger-bg': '#fee2e2',
  },
}

export const radius = { sm: '8px', md: '10px', lg: '12px', pill: '999px' }
export const font = "'Inter Variable', Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"

/** CSS de variables: dark por defecto (:root) y override por [data-theme]. */
export function buildThemeCss(): string {
  const vars = (t: Tokens) => Object.entries(t).map(([k, v]) => `--c-${k}:${v}`).join(';')
  const r = Object.entries(radius).map(([k, v]) => `--r-${k}:${v}`).join(';')
  return `:root,[data-theme="dark"]{${vars(tokens.dark)};${r};--font:${font};color-scheme:dark}` +
    `[data-theme="light"]{${vars(tokens.light)};color-scheme:light}`
}

// WCAG 2.x contrast
function lum(hex: string): number {
  const n = hex.replace('#', '')
  const c = [0, 2, 4].map(i => parseInt(n.slice(i, i + 2), 16) / 255)
    .map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
export function contrast(a: string, b: string): number {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}
