import type { HTMLAttributes } from 'react'

import { useDropdownContext } from './context'

import styles from './Dropdown.module.css'

type DropdownContentProps = HTMLAttributes<HTMLDivElement> & {
  align?: 'start' | 'end'
}

export function DropdownContent({
  align = 'start',
  children,
  className,
  ...props
}: DropdownContentProps) {
  const { open } = useDropdownContext()

  if (!open) {
    return null
  }

  const classNames = [styles.content, styles[align], className]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={classNames} role="menu" {...props}>
      {children}
    </div>
  )
}
