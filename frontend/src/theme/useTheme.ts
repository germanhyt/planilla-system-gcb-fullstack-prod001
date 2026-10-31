import { useCallback, useState } from 'react'
import { getTheme, toggleTheme, type Theme } from './theme'
const ls = () => (typeof localStorage === 'undefined' ? null : localStorage)
export function useTheme(): [Theme, () => void] {
  const [t, setT] = useState<Theme>(() => getTheme(ls()))
  const toggle = useCallback(() => setT(toggleTheme(ls(), document)), [])
  return [t, toggle]
}
