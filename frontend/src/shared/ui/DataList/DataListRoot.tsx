import type { ComponentPropsWithoutRef } from 'react'

import styles from './DataList.module.css'

type DataListRootProps = ComponentPropsWithoutRef<'div'>

export function DataListRoot({
  children,
  className,
  ...props
}: DataListRootProps) {
  return (
    <div
      className={[styles.root, className].filter(Boolean).join(' ')}
      {...props}
    >
      {children}
    </div>
  )
}
