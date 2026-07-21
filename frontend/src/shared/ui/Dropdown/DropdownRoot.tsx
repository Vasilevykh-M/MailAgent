import { useEffect, useRef, useState, type ReactNode } from 'react'

import { DropdownContext } from './context'

import styles from './Dropdown.module.css'

type DropdownRootProps = {
  children: ReactNode
  className?: string
}

export function DropdownRoot({ children, className }: DropdownRootProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const classNames = [styles.root, className].filter(Boolean).join(' ')

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  return (
    <DropdownContext.Provider value={{ open, setOpen }}>
      <div className={classNames} ref={rootRef}>
        {children}
      </div>
    </DropdownContext.Provider>
  )
}
