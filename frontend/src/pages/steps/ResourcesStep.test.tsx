import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import ResourcesStep from './ResourcesStep'
import {
  generateReferenceImage,
  generateResourceImages,
  getProviderModels,
  getProviders,
  listResources,
  updateProject,
} from '@/lib/api'
import type { Project, Resource } from '@/types'

vi.mock('@/lib/api', () => ({
  listResources: vi.fn(),
  createResource: vi.fn(),
  createVariant: vi.fn(),
  updateResource: vi.fn(),
  updateVariant: vi.fn(),
  generateResources: vi.fn(),
  generateResourceImages: vi.fn(),
  uploadReferenceImage: vi.fn(),
  assetUrl: vi.fn(),
  generateReferenceImage: vi.fn(),
  getProviders: vi.fn(),
  getProviderModels: vi.fn(),
  getVoices: vi.fn().mockResolvedValue([]),
  updateProject: vi.fn(),
  getJob: vi.fn(),
  cancelJob: vi.fn(),
}))

const project: Project = {
  id: 1,
  name: 'P',
  synopsis: '',
  video_style: '',
  aspect_ratio: '16:9',
  status: 'draft',
  settings: { image_provider: 'gemini' },
  created_at: '',
  updated_at: '',
}

const resource: Resource = {
  id: 1,
  project_id: 1,
  type: 'character',
  name: 'Kai',
  profile: {},
  variants: [
    {
      id: 11,
      resource_id: 1,
      name: 'Base',
      description: 'héroe con espada',
      episodes: [],
      image_model: '',
      image_style: '',
      voice: {},
      reference_images: [],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listResources).mockResolvedValue([resource])
  vi.mocked(getProviders).mockResolvedValue({
    llm: [{ name: 'ollama', configured: true }],
    image: [{ name: 'gemini', configured: true }, { name: 'upload', configured: true }],
    video: [{ name: 'mock', configured: true }],
    tts: [{ name: 'edge', configured: true }],
  })
  vi.mocked(updateProject).mockResolvedValue(project)
  vi.mocked(getProviderModels).mockResolvedValue([])
})

test('generates image for variant with prompt', async () => {
  vi.mocked(generateReferenceImage).mockResolvedValue([
    { id: 9, variant_id: 11, path: 'p/9.png', origin: 'generated', kind: 'reference' },
  ])
  const user = userEvent.setup()

  render(<ResourcesStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: 'Kai' }))

  const promptInput = await screen.findByLabelText('Descripción / prompt')
  await user.clear(promptInput)
  await user.type(promptInput, 'con armadura dorada')
  await user.click(screen.getByRole('button', { name: 'Generar' }))

  await waitFor(() =>
    expect(generateReferenceImage).toHaveBeenCalledWith(11, {
      prompt: 'con armadura dorada',
    }),
  )
})

test('persists image provider change in project settings', async () => {
  const user = userEvent.setup()
  render(<ResourcesStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('combobox', { name: 'Imágenes' }))
  const option = await screen.findByRole('option', { name: 'upload' })
  await user.click(option)

  await waitFor(() =>
    expect(updateProject).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        settings: expect.objectContaining({ image_provider: 'upload' }),
      }),
    ),
  )
})

test('persists image model in project settings', async () => {
  vi.mocked(getProviderModels).mockResolvedValue([
    { id: 'fal-ai/flux/dev', name: 'Flux Dev', description: '' },
  ])
  const user = userEvent.setup()
  render(<ResourcesStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('combobox', { name: 'Imágenes (modelo)' }))
  const option = await screen.findByRole('option', { name: 'Flux Dev' })
  await user.click(option)

  await waitFor(() =>
    expect(updateProject).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        settings: expect.objectContaining({ image_model: 'fal-ai/flux/dev' }),
      }),
    ),
  )
})

test('generates images in batch for the selected resources', async () => {
  vi.mocked(generateResourceImages).mockResolvedValue({
    id: 7,
    type: 'resource_image_gen',
    status: 'queued',
    progress: 0,
    payload: {},
    result: {},
    error: null,
    parent_id: null,
    project_id: 1,
    created_at: '',
    updated_at: '',
  })
  const user = userEvent.setup()
  render(<ResourcesStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByLabelText('Seleccionar Kai'))
  await user.click(screen.getByRole('button', { name: /Generar imágenes/ }))

  await waitFor(() =>
    expect(generateResourceImages).toHaveBeenCalledWith(1, {
      resource_ids: [1],
      provider: 'gemini',
      model: undefined,
    }),
  )
})
