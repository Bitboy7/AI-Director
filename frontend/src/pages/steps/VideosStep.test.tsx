import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import VideosStep from './VideosStep'
import {
  assembleEpisode,
  createFragment,
  generateFragment,
  generateStoryboards,
  getJob,
  getProviderModels,
  getProviders,
  getResolutions,
  listEpisodes,
  listResources,
  updateFragment,
  updateProject,
} from '@/lib/api'
import type { Episode, Job, Project } from '@/types'

vi.mock('@/lib/api', () => ({
  listEpisodes: vi.fn(),
  listResources: vi.fn(),
  listJobs: vi.fn().mockResolvedValue([]),
  getCostEstimate: vi.fn().mockResolvedValue({ episodes: [], total: { fragments: 0, seconds: 0, cost_usd: 0 } }),
  generateEpisode: vi.fn(),
  assembleEpisode: vi.fn(),
  generateFragment: vi.fn(),
  generateStoryboards: vi.fn(),
  generateFragmentReference: vi.fn(),
  uploadFragmentReference: vi.fn(),
  updateStoryboardPanel: vi.fn(),
  createStoryboardPanel: vi.fn(),
  deleteStoryboardPanel: vi.fn(),
  createFragment: vi.fn(),
  deleteFragment: vi.fn(),
  selectFragmentVideo: vi.fn(),
  getResolutions: vi.fn(),
  exportEpisodeUrl: vi.fn((id: number) => `/api/v1/episodes/${id}/final?download=1`),
  episodeFinalUrl: vi.fn((id: number) => `/api/v1/episodes/${id}/final`),
  assetUrl: vi.fn(),
  getProviders: vi.fn(),
  getProviderModels: vi.fn(),
  updateProject: vi.fn(),
  updateFragment: vi.fn(),
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
  settings: { video_provider: 'mock' },
  created_at: '',
  updated_at: '',
}

const makeJob = (id: number): Job => ({
  id,
  type: 'episode_assembly',
  status: 'running',
  progress: 0,
  payload: {},
  result: {},
  error: null,
  parent_id: null,
  project_id: 1,
  created_at: '',
  updated_at: '',
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listEpisodes).mockResolvedValue([])
  vi.mocked(listResources).mockResolvedValue([])
  vi.mocked(getProviders).mockResolvedValue({
    llm: [{ name: 'ollama', configured: true }],
    image: [{ name: 'gemini', configured: true }],
    video: [{ name: 'mock', configured: true }, { name: 'omni', configured: true }],
    tts: [{ name: 'edge', configured: true }],
  })
  vi.mocked(updateProject).mockResolvedValue(project)
  vi.mocked(updateFragment).mockResolvedValue(episode.fragments[0])
  vi.mocked(getProviderModels).mockResolvedValue([])
  vi.mocked(getResolutions).mockResolvedValue([{ label: '1280×720' }])
  vi.mocked(getJob).mockResolvedValue(makeJob(1))
})

test('persists video provider change in project settings', async () => {
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('combobox', { name: 'Proveedor de video' }))
  const option = await screen.findByRole('option', { name: 'omni' })
  await user.click(option)

  await waitFor(() =>
    expect(updateProject).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        settings: expect.objectContaining({ video_provider: 'omni' }),
      }),
    ),
  )
})

const episode: Episode = {
  id: 5,
  project_id: 1,
  number: 1,
  title: 'Piloto',
  script: {},
  status: 'scripted',
  fragments: [
    {
      id: 50,
      episode_id: 5,
      shot_number: 1,
      time_place: 'Calle',
      cast: [],
      prompt_video: 'Kai camina',
      duration: 10,
      status: 'pending',
      video_path: null,
      video_provider: null,
      video_model: null,
      resolution: null,
      cost_usd: 0,
      dialogue_lines: [],
      storyboard: [
        {
          id: 1,
          fragment_id: 50,
          order: 0,
          title: 'Inicio',
          start_seconds: 0,
          end_seconds: 4,
          prompt: 'wide shot',
        },
      ],
      reference_images: [],
      videos: [],
    },
  ],
}

test('adds a new plan to the episode', async () => {
  vi.mocked(listEpisodes).mockResolvedValue([episode])
  vi.mocked(createFragment).mockResolvedValue(episode.fragments[0])
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: /Añadir plano/ }))

  await waitFor(() =>
    expect(createFragment).toHaveBeenCalledWith(5, expect.objectContaining({ shot_number: 2 })),
  )
})

test('changes the project aspect ratio', async () => {
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: '9:16' }))

  await waitFor(() =>
    expect(updateProject).toHaveBeenCalledWith(1, expect.objectContaining({ aspect_ratio: '9:16' })),
  )
})

test('shows the export link when the episode is fully generated', async () => {
  const generated: Episode = {
    ...episode,
    fragments: episode.fragments.map((fragment) => ({
      ...fragment,
      status: 'generated',
      video_path: 'v.mp4',
    })),
  }
  vi.mocked(listEpisodes).mockResolvedValue([generated])
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  const link = await screen.findByRole('link', { name: /Exportar capítulo/ })
  expect(link).toHaveAttribute('href', '/api/v1/episodes/5/final?download=1')
})

const generatedEpisode: Episode = {
  ...episode,
  fragments: episode.fragments.map((fragment) => ({
    ...fragment,
    status: 'generated',
    video_path: '1/videos/50.mp4',
  })),
}

test('disables rendering the chapter until every plan is generated', async () => {
  vi.mocked(listEpisodes).mockResolvedValue([episode])
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  expect(await screen.findByRole('button', { name: /Renderizar capítulo/ })).toBeDisabled()
})

test('assembles the chapter and plays the render effect', async () => {
  vi.mocked(listEpisodes).mockResolvedValue([generatedEpisode])
  vi.mocked(assembleEpisode).mockResolvedValue(makeJob(77))
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: /Renderizar capítulo/ }))

  await waitFor(() => expect(assembleEpisode).toHaveBeenCalledWith(5))
  expect(await screen.findByText(/Renderizando capítulo/)).toBeInTheDocument()
})

test('re-renders an already assembled chapter', async () => {
  const assembled: Episode = { ...generatedEpisode, status: 'assembled' }
  vi.mocked(listEpisodes).mockResolvedValue([assembled])
  vi.mocked(assembleEpisode).mockResolvedValue(makeJob(78))
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: /Volver a renderizar/ }))

  await waitFor(() => expect(assembleEpisode).toHaveBeenCalledWith(5))
  expect(await screen.findByText(/Renderizando capítulo/)).toBeInTheDocument()
})

test('regenerates a single plan after confirmation', async () => {
  vi.mocked(listEpisodes).mockResolvedValue([generatedEpisode])
  vi.mocked(generateFragment).mockResolvedValue(makeJob(88))
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: 'Regenerar plano 1-1' }))
  await user.click(await screen.findByRole('button', { name: 'Regenerar plano' }))

  await waitFor(() => expect(generateFragment).toHaveBeenCalledWith(50))
})

test('requests storyboards for the selected episode', async () => {
  vi.mocked(listEpisodes).mockResolvedValue([episode])
  vi.mocked(generateStoryboards).mockResolvedValue({
    id: 9,
    type: 'storyboard_gen',
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
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: /Generar storyboards/ }))

  await waitFor(() =>
    expect(generateStoryboards).toHaveBeenCalledWith(1, { episode_ids: [5] }),
  )
  expect(await screen.findByLabelText('panel-1')).toHaveValue('wide shot')
})

test('saves provider, model and resolution overrides per plan', async () => {
  vi.mocked(listEpisodes).mockResolvedValue([episode])
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('combobox', { name: 'Proveedor' }))
  await user.click(await screen.findByRole('option', { name: 'omni' }))

  await waitFor(() =>
    expect(updateFragment).toHaveBeenCalledWith(50, {
      video_provider: 'omni',
      video_model: null,
    }),
  )
})

test('resets a plan back to the project defaults', async () => {
  const overridden: Episode = {
    ...episode,
    fragments: episode.fragments.map((fragment) => ({
      ...fragment,
      video_provider: 'omni',
      video_model: 'gemini-omni-1.1-flash',
      resolution: '720p',
    })),
  }
  vi.mocked(listEpisodes).mockResolvedValue([overridden])
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(
    await screen.findByRole('button', { name: 'Restablecer ajustes del plano 1-1' }),
  )

  await waitFor(() =>
    expect(updateFragment).toHaveBeenCalledWith(50, {
      video_provider: null,
      video_model: null,
      resolution: null,
    }),
  )
})

test('shows the per-second price for each video model', async () => {
  vi.mocked(listEpisodes).mockResolvedValue([episode])
  vi.mocked(getProviderModels).mockResolvedValue([
    {
      id: 'gemini-omni-1.1-flash',
      name: 'Omni Flash',
      description: '',
      pricing: { unit: 'second', usd: 0.03 },
    },
  ])
  const user = userEvent.setup()
  render(<VideosStep project={project} onProjectUpdated={vi.fn()} />)

  await user.click(await screen.findByRole('combobox', { name: 'Proveedor (modelo)' }))

  expect(await screen.findByRole('option', { name: /Omni Flash/ })).toHaveTextContent('$0.030/s')
})
