import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { MultiSelect } from './MultiSelect'

function MultiSelectHarness() {
  const [value, setValue] = useState<string[]>([])

  return (
    <MultiSelect
      ariaLabel="Выбор класса"
      onChange={setValue}
      options={[
        { label: 'Станки', value: 'MACHINES' },
        { label: 'Химия', value: 'CHEMISTRY' },
      ]}
      placeholder="Все"
      value={value}
    />
  )
}

describe('MultiSelect', () => {
  afterEach(cleanup)

  it('connects trigger and popup and restores focus on Escape', async () => {
    const user = userEvent.setup()
    render(<MultiSelectHarness />)

    const trigger = screen.getByRole('button', { name: 'Все' })
    await user.click(trigger)

    const popup = screen.getByRole('dialog', { name: 'Выбор класса' })
    expect(trigger).toHaveAttribute('aria-controls', popup.id)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('checkbox', { name: 'Станки' })).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
