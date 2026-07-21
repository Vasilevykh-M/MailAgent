import type { ComponentPropsWithoutRef, ReactNode } from 'react'

import styles from './DataList.module.css'

export type DataListItemProps = Omit<
  ComponentPropsWithoutRef<'button'>,
  'title'
> & {
  badge?: ReactNode
  description?: ReactNode
  meta?: ReactNode[]
  selected?: boolean
  title: ReactNode
}

export function DataListItem({
  badge,
  className,
  description,
  meta = [],
  selected = false,
  title,
  type = 'button',
  ...props
}: DataListItemProps) {
  return (
    <button
      aria-pressed={selected}
      className={[styles.item, selected ? styles.selected : '', className]
        .filter(Boolean)
        .join(' ')}
      type={type}
      {...props}
    >
      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        {badge}
      </div>
      {description && <p className={styles.description}>{description}</p>}
      {meta.length > 0 && (
        <div className={styles.meta}>
          {meta.map((item, index) => (
            <span className={styles.metaItem} key={index}>
              {item}
            </span>
          ))}
        </div>
      )}
    </button>
  )
}
