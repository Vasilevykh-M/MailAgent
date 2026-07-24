import {
  createContext,
  useContext,
  type Dispatch,
  type SetStateAction,
} from 'react'

export type DropdownContextValue = {
  contentId: string
  open: boolean
  setOpen: Dispatch<SetStateAction<boolean>>
}

export const DropdownContext = createContext<DropdownContextValue | null>(null)

export function useDropdownContext() {
  const context = useContext(DropdownContext)

  if (!context) {
    throw new Error('Dropdown components must be used inside <Dropdown>')
  }

  return context
}
