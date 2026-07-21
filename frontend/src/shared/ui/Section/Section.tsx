import type { ComponentPropsWithoutRef, ReactNode } from 'react'

import styles from './Section.module.css'

type SectionProps = ComponentPropsWithoutRef<'section'> & {
  actions?: ReactNode
  title?: ReactNode
}

export function Section({
  actions,
  children,
  className,
  title,
  ...props
}: SectionProps) {
  const classNames = [styles.section, className].filter(Boolean).join(' ')

  return (
    <section className={classNames} {...props}>
      {(title || actions) && (
        <header className={styles.header}>
          {title && <h3>{title}</h3>}
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}
