import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
