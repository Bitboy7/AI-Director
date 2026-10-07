import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import ProviderSelector from './ProviderSelector'
import { getProviderModels, getProviders } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getProviders: vi.fn(),
  getProviderModels: vi.fn(),
}))

const fullCatalog = {
  llm: [{ name: 'ollama', configured: true }],
  image: [{ name: 'gemini', configured: false }, { name: 'fal', configured: true }],
  video: [{ name: 'mock', configured: true }, { name: 'omni', configured: false }],
  tts: [{ name: 'edge', configured: true }],
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getProviderModels).mockResolvedValue([])
})

test('renders options and reports selection', async () => {
  vi.mocked(getProviders).mockResolvedValue(fullCatalog)
  const onChange = vi.fn()
  const user = userEvent.setup()

  render(<ProviderSelector kind="video" value="mock" label="Proveedor de video" onChange={onChange} />)

  expect(await screen.findByText('Proveedor de video')).toBeInTheDocument()
  await user.click(await screen.findByRole('combobox', { name: 'Proveedor de video' }))
  const option = await screen.findByRole('option', { name: 'mock' })
  await user.click(option)

  expect(onChange).toHaveBeenCalledWith('mock')
})

test('filters out providers that are not configured', async () => {
  vi.mocked(getProviders).mockResolvedValue(fullCatalog)
  const user = userEvent.setup()

  render(<ProviderSelector kind="image" value="fal" label="Imágenes" onChange={vi.fn()} />)

  await user.click(await screen.findByRole('combobox', { name: 'Imágenes' }))

  expect(await screen.findByRole('option', { name: 'fal' })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'gemini' })).not.toBeInTheDocument()
})

test('keeps current value visible even when not configured', async () => {
  vi.mocked(getProviders).mockResolvedValue(fullCatalog)
  const user = userEvent.setup()

  render(<ProviderSelector kind="image" value="gemini" label="Imágenes" onChange={vi.fn()} />)

  await user.click(await screen.findByRole('combobox', { name: 'Imágenes' }))

  expect(await screen.findByRole('option', { name: 'gemini' })).toBeInTheDocument()
})

test('falls back to current value when catalog is empty', async () => {
  vi.mocked(getProviders).mockResolvedValue({ llm: [], image: [], video: [], tts: [] })

  render(
    <ProviderSelector kind="image" value="gemini" label="Imágenes" onChange={vi.fn()} />,
  )

  expect(await screen.findByText('gemini')).toBeInTheDocument()
})

test('fetches and selects models for the provider', async () => {
  vi.mocked(getProviders).mockResolvedValue(fullCatalog)
  vi.mocked(getProviderModels).mockResolvedValue([
    { id: 'fal-ai/flux/dev', name: 'Flux Dev', description: '' },
    { id: 'fal-ai/nano-banana-2', name: 'Nano Banana 2', description: '' },
  ])
  const onModelChange = vi.fn()
  const user = userEvent.setup()

  render(
    <ProviderSelector
      kind="image"
      value="fal"
      label="Imágenes"
      onChange={vi.fn()}
      model=""
      onModelChange={onModelChange}
    />,
  )

  expect(await screen.findByRole('combobox', { name: 'Imágenes (modelo)' })).toBeInTheDocument()
  await user.click(screen.getByRole('combobox', { name: 'Imágenes (modelo)' }))
  const option = await screen.findByRole('option', { name: 'Flux Dev' })
  await user.click(option)

  expect(onModelChange).toHaveBeenCalledWith('fal-ai/flux/dev')
})
