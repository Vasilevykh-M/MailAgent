import type { ButtonHTMLAttributes } from 'react'

import styles from './Button.module.css'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
}

export function Button({
  variant = 'secondary',
  className,
  children,
  ...props
}: ButtonProps) {
  const classNames = [styles.button, styles[variant], className]
    .filter(Boolean)
    .join(' ')

  return (
    <button className={classNames} type="button" {...props}>
      {children}
    </button>
  )
}
