import { Moon, Sun } from 'lucide-react'

import { useTheme } from '../../theme'

import styles from './ThemeSwitch.module.css'

export function ThemeSwitch() {
  const { theme, toggleTheme } = useTheme()
  const isLight = theme === 'light'

  return (
    <button
      aria-label={isLight ? 'Включить тёмную тему' : 'Включить светлую тему'}
      aria-pressed={isLight}
      className={`${styles.switch} ${isLight ? styles.light : ''}`}
      onClick={toggleTheme}
      title={isLight ? 'Включить тёмную тему' : 'Включить светлую тему'}
      type="button"
    >
      <span className={styles.thumb}>
        {isLight ? (
          <Sun aria-hidden="true" size={12} />
        ) : (
          <Moon aria-hidden="true" size={12} />
        )}
      </span>
    </button>
  )
}
