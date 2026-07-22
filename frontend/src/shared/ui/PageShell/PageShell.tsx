import type { ReactNode } from 'react'

import { ThemeSwitch } from '../ThemeSwitch'

import styles from './PageShell.module.css'

type PageShellProps = {
  actions?: ReactNode
  children: ReactNode
  navigation?: ReactNode
  title: ReactNode
}

export function PageShell({
  actions,
  children,
  navigation,
  title,
}: PageShellProps) {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <div className={styles.headerRow}>
            <h1 className={styles.brand}>{title}</h1>
            {navigation}
            <div className={styles.actions}>
              {actions}
              <ThemeSwitch />
            </div>
          </div>
        </header>
        <div className={styles.content}>{children}</div>
      </div>
    </main>
  )
}
