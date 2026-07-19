import type { ComponentPropsWithoutRef } from 'react'

import styles from './Badge.module.css'

export type BadgeTone =
  | 'neutral'
  | 'accent'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'

type BadgeProps = ComponentPropsWithoutRef<'span'> & {
  tone?: BadgeTone
}

export function Badge({
  tone = 'neutral',
  className,
  children,
  ...props
}: BadgeProps) {
  const classNames = [styles.badge, styles[tone], className]
    .filter(Boolean)
    .join(' ')

  return (
    <span className={classNames} {...props}>
      {children}
    </span>
  )
}
