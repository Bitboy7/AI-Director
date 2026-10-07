import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import StyleSelect from './StyleSelect'
import { getStyles } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getStyles: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getStyles).mockResolvedValue([
    { id: 'anime', label: 'Anime' },
    { id: 'cyberpunk', label: 'Cyberpunk' },
  ])
})

test('renders styles and reports the selected id', async () => {
  const onChange = vi.fn()
  const user = userEvent.setup()
  render(<StyleSelect value="" onChange={onChange} label="Estilo" />)

  await user.click(await screen.findByRole('combobox', { name: 'Estilo' }))
  await user.click(await screen.findByRole('option', { name: 'Cyberpunk' }))

  expect(onChange).toHaveBeenCalledWith('cyberpunk')
})

test('maps the "Sin estilo" option to an empty value', async () => {
  const onChange = vi.fn()
  const user = userEvent.setup()
  render(<StyleSelect value="anime" onChange={onChange} label="Estilo" />)

  await user.click(await screen.findByRole('combobox', { name: 'Estilo' }))
  await user.click(await screen.findByRole('option', { name: 'Sin estilo' }))

  expect(onChange).toHaveBeenCalledWith('')
})
