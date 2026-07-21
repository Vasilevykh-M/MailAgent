import type { ReactNode } from 'react'

import styles from './FileItem.module.css'

type FileItemProps = {
  actions?: ReactNode
  description?: ReactNode
  facts?: ReactNode[]
  meta?: ReactNode
  title: ReactNode
}

export function FileItem({
  actions,
  description,
  facts = [],
  meta,
  title,
}: FileItemProps) {
  return (
    <article className={styles.item}>
      <div className={styles.content}>
        <div className={styles.header}>
          <p className={styles.title}>{title}</p>
          {meta && <span>{meta}</span>}
        </div>
        {description && <p className={styles.description}>{description}</p>}
        {facts.length > 0 && (
          <div className={styles.factsBlock}>
            <p>Ключевые факты</p>
            <ul className={styles.facts}>
              {facts.map((fact, index) => (
                <li key={index}>{fact}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </article>
  )
}
