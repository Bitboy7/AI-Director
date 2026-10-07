import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'
import Settings from './Settings'
import { getCredentials, verifyCredential } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getCredentials: vi.fn(),
  putCredentials: vi.fn(),
  deleteCredential: vi.fn(),
  verifyCredential: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

test('renders provider cards with green check for verified provider', async () => {
  vi.mocked(getCredentials).mockResolvedValue({
    seedance: { api_key: 'sk-123' },
    ollama: {},
  })
  vi.mocked(verifyCredential).mockImplementation(async (provider: string) =>
    provider === 'ollama'
      ? { status: 'ok', detail: 'respondiendo' }
      : { status: 'unavailable', detail: 'sin verificador' },
  )

  render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  )

  expect(await screen.findByText('seedance')).toBeInTheDocument()
  expect(screen.getByText('ollama')).toBeInTheDocument()
  expect(await screen.findByTitle('verificado')).toBeInTheDocument()
  expect(screen.getAllByTitle('no verificable').length).toBeGreaterThan(0)
})

test('shows stored api key value', async () => {
  vi.mocked(getCredentials).mockResolvedValue({ seedance: { api_key: 'sk-999' } })
  vi.mocked(verifyCredential).mockResolvedValue({ status: 'unavailable', detail: '' })

  render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  )

  expect(await screen.findByDisplayValue('sk-999')).toBeInTheDocument()
})

test('back button navigates to previous page', async () => {
  vi.mocked(getCredentials).mockResolvedValue({})
  vi.mocked(verifyCredential).mockResolvedValue({ status: 'unavailable', detail: '' })
  const user = userEvent.setup()

  render(
    <MemoryRouter initialEntries={['/dashboard', '/settings']}>
      <Routes>
        <Route path="/settings" element={<Settings />} />
        <Route path="/dashboard" element={<div>Dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  )

  const back = await screen.findByRole('button', { name: /Volver|Atrás/i })
  await user.click(back)

  expect(await screen.findByText('Dashboard')).toBeInTheDocument()
})
