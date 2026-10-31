// Design tokens (fuente única). Estilo "HR Payroll Dashboard": SaaS limpio, acentos azul/ámbar/teal.
export type Theme = 'dark' | 'light'
export type Tokens = Record<string, string>

export const tokens: Record<Theme, Tokens> = {
  dark: {
    bg: '#0b1220', surface: '#111a2e', 'surface-2': '#17223a', border: '#24314d',
    text: '#e6ebf5', muted: '#9aa8c2',
    primary: '#f1f5f9', 'primary-fg': '#0b1220',
    'pill-active': '#1e2a44',
    blue: '#60a5fa', amber: '#fbbf24', teal: '#2dd4bf',
    success: '#4ade80', 'success-bg': '#0f2e22',
    warning: '#fbbf24', 'warning-bg': '#33270b',
    danger: '#f87171', 'danger-bg': '#3a1515',
  },
  light: {
    bg: '#f5f6f8', surface: '#ffffff', 'surface-2': '#f1f3f6', border: '#e4e7ec',
    text: '#111827', muted: '#5b6474',
    primary: '#111827', 'primary-fg': '#ffffff',
    'pill-active': '#ffffff',
    blue: '#2563eb', amber: '#b45309', teal: '#0f766e',
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
