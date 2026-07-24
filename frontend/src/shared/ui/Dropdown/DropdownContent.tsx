import { useEffect, useRef, type HTMLAttributes } from 'react'

import { useDropdownContext } from './context'

import styles from './Dropdown.module.css'

type DropdownContentProps = HTMLAttributes<HTMLDivElement> & {
  align?: 'start' | 'end'
}

export function DropdownContent({
  align = 'start',
  children,
  className,
  role = 'dialog',
  ...props
}: DropdownContentProps) {
  const { contentId, open } = useDropdownContext()
  const contentRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) {
      return
    }

    const content = contentRef.current
    const firstFocusable = content?.querySelector<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    const focusTarget = firstFocusable ?? content

    focusTarget?.focus()
  }, [open])

  if (!open) {
    return null
  }

  const classNames = [styles.content, styles[align], className]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={classNames}
      id={contentId}
      ref={contentRef}
      role={role}
      tabIndex={-1}
      {...props}
    >
      {children}
    </div>
  )
}
