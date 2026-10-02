import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'
import ProjectView from './ProjectView'
import { getProject, listEpisodes, listResources } from '@/lib/api'
import type { Project } from '@/types'

vi.mock('@/lib/api', () => ({
  getProject: vi.fn(),
  setPhaseCompleted: vi.fn(),
  listEpisodes: vi.fn(),
  listResources: vi.fn(),
  generateScript: vi.fn(),
  generateResources: vi.fn(),
  generateEpisode: vi.fn(),
  generateFragment: vi.fn(),
  getJob: vi.fn(),
  cancelJob: vi.fn(),
}))

const project = (completedPhases: number[]): Project => ({
  id: 1,
  name: 'Neon Rebellion',
  synopsis: '',
  video_style: '',
  aspect_ratio: '16:9',
  status: 'draft',
  settings: { completed_phases: completedPhases },
  created_at: '',
  updated_at: '',
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listEpisodes).mockResolvedValue([])
  vi.mocked(listResources).mockResolvedValue([])
})

function renderView(project: Project) {
  vi.mocked(getProject).mockResolvedValue(project)
  return render(
    <MemoryRouter initialEntries={['/projects/1']}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectView />} />
      </Routes>
    </MemoryRouter>,
  )
}

test('phase 2 locked until phase 1 completed', async () => {
  renderView(project([]))
  expect(await screen.findByRole('tab', { name: /Esquema del guion/ })).toBeInTheDocument()
  const tab2 = screen.getByRole('tab', { name: /Biblioteca de recursos/ })
  expect(tab2).toHaveAttribute('aria-disabled', 'true')
})

test('phase 2 unlocked after phase 1 completed, phase 3 still locked', async () => {
  renderView(project([1]))
  const tab2 = await screen.findByRole('tab', { name: /Biblioteca de recursos/ })
  expect(tab2).not.toHaveAttribute('aria-disabled', 'true')
  const tab3 = screen.getByRole('tab', { name: /Videos por episodio/ })
  expect(tab3).toHaveAttribute('aria-disabled', 'true')
})

test('shows complete phase button and marks phase completed', async () => {
  renderView(project([]))
  const button = await screen.findByRole('button', { name: /Marcar fase 1 como completada/ })
  expect(button).toBeInTheDocument()
})
