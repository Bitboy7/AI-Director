import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import MentionTextarea from './MentionTextarea'
import type { Resource } from '@/types'

const resources: Resource[] = [
  { id: 1, project_id: 1, type: 'character', name: 'Goku', profile: {}, variants: [] },
  { id: 2, project_id: 1, type: 'scene', name: 'Calle', profile: {}, variants: [] },
]

function Harness({ onChange }: { onChange?: (value: string) => void }) {
  const [value, setValue] = useState('')
  return (
    <MentionTextarea
      value={value}
      onChange={(next) => {
        setValue(next)
        onChange?.(next)
      }}
      resources={resources}
    />
  )
}

test('opens the mention menu on @ and inserts the name', async () => {
  const user = userEvent.setup()
  const onChange = vi.fn()
  render(<Harness onChange={onChange} />)

  const textarea = screen.getByPlaceholderText(/Escribe @/)
  await user.type(textarea, 'Veo a @')

  expect(await screen.findByText('Personajes')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Goku' }))

  expect(onChange).toHaveBeenCalledWith('Veo a @Goku ')
})

test('filters resources by the typed query', async () => {
  const user = userEvent.setup()
  render(<Harness />)

  const textarea = screen.getByPlaceholderText(/Escribe @/)
  await user.type(textarea, '@gok')

  expect(await screen.findByRole('button', { name: 'Goku' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Calle' })).not.toBeInTheDocument()
})
