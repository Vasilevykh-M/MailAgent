import { createContext, useContext } from 'react'

export type DropdownContextValue = {
  open: boolean
  setOpen: (open: boolean) => void
}

export const DropdownContext = createContext<DropdownContextValue | null>(null)

export function useDropdownContext() {
  const context = useContext(DropdownContext)

  if (!context) {
    throw new Error('Dropdown components must be used inside <Dropdown>')
  }

  return context
}
