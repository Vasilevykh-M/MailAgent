import type { ReactNode } from 'react'

import type { BadgeTone } from '../Badge'

import styles from './Alert.module.css'

type AlertTone = Extract<BadgeTone, 'info' | 'success' | 'warning' | 'danger'>

type AlertProps = {
  title: ReactNode
  children?: ReactNode
  tone?: AlertTone
}

export function Alert({ title, children, tone = 'info' }: AlertProps) {
  return (
    <div
      className={`${styles.alert} ${styles[tone]}`}
      role={tone === 'danger' ? 'alert' : 'status'}
    >
      <p className={styles.title}>{title}</p>
      {children && <div className={styles.content}>{children}</div>}
    </div>
  )
}
