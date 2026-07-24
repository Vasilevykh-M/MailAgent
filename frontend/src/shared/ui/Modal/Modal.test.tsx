import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { Modal } from './Modal'

function ModalHarness() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button onClick={() => setOpen(true)} type="button">
        Открыть
      </button>
      {open && (
        <Modal onClose={() => setOpen(false)} title="Детали письма">
          <button type="button">Действие</button>
        </Modal>
      )}
    </>
  )
}

describe('Modal', () => {
  afterEach(cleanup)

  it('traps focus and restores it after Escape', async () => {
    const user = userEvent.setup()
    render(<ModalHarness />)

    const trigger = screen.getByRole('button', { name: 'Открыть' })
    await user.click(trigger)

    const closeButton = screen.getByRole('button', {
      name: 'Закрыть окно письма',
    })
    const actionButton = screen.getByRole('button', { name: 'Действие' })

    expect(
      screen.getByRole('dialog', { name: 'Детали письма' }),
    ).toBeInTheDocument()
    expect(closeButton).toHaveFocus()

    await user.tab()
    expect(actionButton).toHaveFocus()
    await user.tab()
    expect(closeButton).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
