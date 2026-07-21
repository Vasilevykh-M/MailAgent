import { ChevronDown } from 'lucide-react'
import type { ComponentPropsWithoutRef, ReactNode } from 'react'

import styles from './Collapsible.module.css'

type CollapsibleProps = ComponentPropsWithoutRef<'details'> & {
  title: ReactNode
}

export function Collapsible({
  children,
  className,
  title,
  ...props
}: CollapsibleProps) {
  const classNames = [styles.collapsible, className].filter(Boolean).join(' ')

  return (
    <details className={classNames} {...props}>
      <summary>
        <span>{title}</span>
        <ChevronDown aria-hidden="true" className={styles.icon} size={16} />
      </summary>
      <div className={styles.body}>{children}</div>
    </details>
  )
}
