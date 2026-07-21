import {
  Children,
  cloneElement,
  isValidElement,
  type ButtonHTMLAttributes,
  type ReactElement,
} from 'react'

import { useDropdownContext } from './context'

type TriggerElement = ReactElement<ButtonHTMLAttributes<HTMLButtonElement>>

type DropdownTriggerProps = {
  children: TriggerElement
}

export function DropdownTrigger({ children }: DropdownTriggerProps) {
  const { open, setOpen } = useDropdownContext()
  const child = Children.only(children)

  if (!isValidElement<ButtonHTMLAttributes<HTMLButtonElement>>(child)) {
    return null
  }

  return cloneElement(child, {
    'aria-expanded': open,
    'aria-haspopup': 'menu',
    onClick: (event) => {
      child.props.onClick?.(event)
      setOpen(!open)
    },
  })
}
