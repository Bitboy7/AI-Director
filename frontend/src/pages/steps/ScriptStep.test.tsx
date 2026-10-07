import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import ScriptStep from './ScriptStep'
import { getProviderModels, getProviders, getScriptDraft, getStyles, updateProject } from '@/lib/api'
import { confirmScript } from '@/lib/api'
import type { Project } from '@/types'

vi.mock('@/lib/api', () => ({
  generateScript: vi.fn(),
  getProviders: vi.fn(),
  getProviderModels: vi.fn(),
  getStyles: vi.fn().mockResolvedValue([]),
  getVoices: vi.fn().mockResolvedValue([]),
  getScriptDraft: vi.fn(),
  confirmScript: vi.fn(),
  DEFAULT_STYLE_ID: 'anime',
  updateProject: vi.fn(),
  getJob: vi.fn(),
  cancelJob: vi.fn(),
}))

const project: Project = {
  id: 1,
  name: 'P',
  synopsis: 'sinopsis',
  video_style: '',
  aspect_ratio: '16:9',
  status: 'draft',
  settings: { llm_provider: 'ollama' },
  created_at: '',
  updated_at: '',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getScriptDraft).mockResolvedValue({ draft: null, confirmed: false })
  vi.mocked(getProviders).mockResolvedValue({
    llm: [{ name: 'ollama', configured: true }, { name: 'openai', configured: true }],
    image: [{ name: 'gemini', configured: true }],
    video: [{ name: 'mock', configured: true }],
    tts: [{ name: 'edge', configured: true }],
  })
  vi.mocked(updateProject).mockResolvedValue(project)
  vi.mocked(getProviderModels).mockResolvedValue([])
  vi.mocked(getStyles).mockResolvedValue([
    { id: 'anime', label: 'Animado' },
    { id: 'cyberpunk', label: 'Cyberpunk' },
  ])
})

test('persists llm provider change in project settings', async () => {
  const user = userEvent.setup()
  render(<ScriptStep project={project} />)

  await user.click(await screen.findByRole('combobox', { name: 'Modelo' }))
  const option = await screen.findByRole('option', { name: 'openai' })
  await user.click(option)

  await waitFor(() =>
    expect(updateProject).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        settings: expect.objectContaining({ llm_provider: 'openai' }),
      }),
    ),
  )
})

test('persists video style change in project', async () => {
  const user = userEvent.setup()
  render(<ScriptStep project={project} />)

  await user.click(await screen.findByRole('combobox', { name: 'Estilo' }))
  const option = await screen.findByRole('option', { name: 'Cyberpunk' })
  await user.click(option)

  await waitFor(() =>
    expect(updateProject).toHaveBeenCalledWith(1, expect.objectContaining({ video_style: 'cyberpunk' })),
  )
})

const draft = {
  synopsis: 'Un drama intenso',
  characters: [{ name: 'Kai', description: 'hacker', tags: [] }],
  scenes: [],
  props: [],
  episodes: [
    {
      number: 1,
      title: 'Piloto',
      shots: [
        {
          shot_number: 1,
          time_place: 'Calle',
          cast: ['Kai'],
          action: 'Kai camina',
          dialogues: [{ character: 'Kai', text: 'Hola' }],
        },
      ],
    },
  ],
}

test('shows the generated script and confirms it', async () => {
  vi.mocked(getScriptDraft).mockResolvedValue({ draft, confirmed: false })
  vi.mocked(confirmScript).mockResolvedValue(project)
  const user = userEvent.setup()
  render(<ScriptStep project={project} />)

  expect(await screen.findByText('Lectura del guion')).toBeInTheDocument()
  expect(screen.getByText('Kai camina')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /Confirmar guion/ }))

  await waitFor(() => expect(confirmScript).toHaveBeenCalledWith(1))
})

test('shows confirmed state when the script is already confirmed', async () => {
  vi.mocked(getScriptDraft).mockResolvedValue({ draft, confirmed: true })
  render(<ScriptStep project={project} />)

  expect(await screen.findByLabelText('Completado')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Confirmar guion/ })).not.toBeInTheDocument()
})
