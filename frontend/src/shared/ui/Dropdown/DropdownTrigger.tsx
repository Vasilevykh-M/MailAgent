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
  popupType?: 'dialog' | 'listbox'
}

export function DropdownTrigger({
  children,
  popupType = 'dialog',
}: DropdownTriggerProps) {
  const { contentId, open, setOpen } = useDropdownContext()
  const child = Children.only(children)

  if (!isValidElement<ButtonHTMLAttributes<HTMLButtonElement>>(child)) {
    return null
  }

  return cloneElement(child, {
    'aria-controls': contentId,
    'aria-expanded': open,
    'aria-haspopup': popupType,
    onClick: (event) => {
      child.props.onClick?.(event)

      if (!event.defaultPrevented) {
        setOpen((current) => !current)
      }
    },
  })
}
