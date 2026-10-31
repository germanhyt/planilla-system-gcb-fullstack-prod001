import { tokens, type Theme } from './tokens'
export type { Theme }
export const THEME_KEY = 'gcb-theme'
export const DEFAULT_THEME: Theme = 'dark'

type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem'>
type Doc = { documentElement: { setAttribute(n: string, v: string): void }; querySelector(s: string): { setAttribute(n: string, v: string): void } | null }

export function getTheme(storage?: Storage | null): Theme {
  try {
    const v = storage?.getItem(THEME_KEY)
    return v === 'light' || v === 'dark' ? v : DEFAULT_THEME
  } catch { return DEFAULT_THEME }
}
export function applyTheme(theme: Theme, doc?: Doc | null): void {
  if (!doc) return
  doc.documentElement.setAttribute('data-theme', theme)
  doc.querySelector('meta[name="theme-color"]')?.setAttribute('content', tokens[theme].bg)
}
export function setTheme(theme: Theme, storage?: Storage | null, doc?: Doc | null): Theme {
  try { storage?.setItem(THEME_KEY, theme) } catch { /* modo privado */ }
  applyTheme(theme, doc)
  return theme
}
export function toggleTheme(storage?: Storage | null, doc?: Doc | null): Theme {
  return setTheme(getTheme(storage) === 'dark' ? 'light' : 'dark', storage, doc)
}
