import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import styles from './Modal.module.css'

type ModalProps = {
  title: string
  children: ReactNode
  onClose: () => void
}

export function Modal({ title, children, onClose }: ModalProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    document.body.classList.add(styles.bodyLocked)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.classList.remove(styles.bodyLocked)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  return createPortal(
    <div
      aria-labelledby="modal-title"
      aria-modal="true"
      className={styles.overlay}
      role="dialog"
    >
      <button
        aria-label="Закрыть окно письма"
        className={styles.backdrop}
        onClick={onClose}
        type="button"
      />
      <div className={styles.dialog}>
        <header className={styles.header}>
          <h2 id="modal-title">{title}</h2>
          <button
            aria-label="Закрыть окно письма"
            className={styles.closeButton}
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </header>
        <div className={styles.content}>{children}</div>
      </div>
    </div>,
    document.body,
  )
}
