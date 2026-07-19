import type { ComponentPropsWithoutRef, ReactNode } from 'react'

import styles from './Card.module.css'

type CardVariant = 'default' | 'muted' | 'strong'

type CardProps = ComponentPropsWithoutRef<'section'> & {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  variant?: CardVariant
}

export function Card({
  title,
  description,
  actions,
  variant = 'default',
  children,
  className,
  ...props
}: CardProps) {
  const classNames = [styles.card, styles[variant], className]
    .filter(Boolean)
    .join(' ')

  return (
    <section className={classNames} {...props}>
      {(title || description || actions) && (
        <header className={styles.header}>
          <div>
            {title && <h2 className={styles.title}>{title}</h2>}
            {description && <p className={styles.description}>{description}</p>}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
