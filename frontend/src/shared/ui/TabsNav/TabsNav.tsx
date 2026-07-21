import { Link } from 'react-router-dom'

import styles from './TabsNav.module.css'

export type TabsNavItem = {
  active?: boolean
  label: string
  to: string
}

type TabsNavProps = {
  ariaLabel: string
  items: TabsNavItem[]
}

export function TabsNav({ ariaLabel, items }: TabsNavProps) {
  return (
    <nav className={styles.nav} aria-label={ariaLabel}>
      {items.map((item) => (
        <Link
          className={`${styles.link} ${item.active ? styles.active : ''}`}
          key={item.to}
          to={item.to}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  )
}
