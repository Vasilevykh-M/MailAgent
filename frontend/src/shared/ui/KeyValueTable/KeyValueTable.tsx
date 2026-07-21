import type { ReactNode } from 'react'

import styles from './KeyValueTable.module.css'

export type KeyValueTableItem = {
  key: string
  label: ReactNode
  value: ReactNode
}

type KeyValueTableProps = {
  items: KeyValueTableItem[]
}

export function KeyValueTable({ items }: KeyValueTableProps) {
  return (
    <dl className={styles.table}>
      {items.map((item) => (
        <div className={styles.row} key={item.key}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}
