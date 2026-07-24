import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

import { DropdownContext } from './context'

import styles from './Dropdown.module.css'

type DropdownRootProps = {
  children: ReactNode
  className?: string
}

export function DropdownRoot({ children, className }: DropdownRootProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const contentId = useId()
  const classNames = [styles.root, className].filter(Boolean).join(' ')

  useEffect(() => {
    if (!open) {
      return
    }

    function handlePointerDown(event: PointerEvent) {
      if (
        !(event.target instanceof Node) ||
        !rootRef.current?.contains(event.target)
      ) {
        setOpen(false)
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        setOpen(false)
        rootRef.current
          ?.querySelector<HTMLButtonElement>(`[aria-controls="${contentId}"]`)
          ?.focus()
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [contentId, open])

  return (
    <DropdownContext.Provider value={{ contentId, open, setOpen }}>
      <div className={classNames} ref={rootRef}>
        {children}
      </div>
    </DropdownContext.Provider>
  )
}
