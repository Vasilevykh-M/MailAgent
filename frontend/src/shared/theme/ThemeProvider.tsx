import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { ThemeContext, type ThemeName } from './context'

const themeStorageKey = 'mail-agent-theme'
const defaultTheme: ThemeName = 'light'

function readStoredTheme(): ThemeName {
  if (typeof window === 'undefined') {
    return defaultTheme
  }

  const value = window.localStorage.getItem(themeStorageKey)

  return value === 'light' || value === 'dark' ? value : defaultTheme
}

type ThemeProviderProps = {
  children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setTheme] = useState(readStoredTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem(themeStorageKey, theme)
  }, [theme])

  const value = useMemo(
    () => ({
      theme,
      toggleTheme: () =>
        setTheme((current) => (current === 'dark' ? 'light' : 'dark')),
    }),
    [theme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
