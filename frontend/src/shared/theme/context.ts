import { createContext } from 'react'

export type ThemeName = 'dark' | 'light'

export type ThemeContextValue = {
  theme: ThemeName
  toggleTheme: () => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
