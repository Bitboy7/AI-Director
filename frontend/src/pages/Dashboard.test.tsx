import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'
import Dashboard from './Dashboard'
import { listProjects } from '@/lib/api'
import type { Project } from '@/types'

vi.mock('@/lib/api', () => ({
  listProjects: vi.fn(),
  createProject: vi.fn(),
  deleteProject: vi.fn(),
}))

const project = (id: number, name: string): Project => ({
  id,
  name,
  synopsis: '',
  video_style: '',
  aspect_ratio: '16:9',
  status: 'draft',
  settings: {},
  created_at: '',
  updated_at: '',
})

beforeEach(() => {
  vi.clearAllMocks()
})

test('renders project cards', async () => {
  vi.mocked(listProjects).mockResolvedValue([project(1, 'Neon Rebellion'), project(2, 'Cyber Vale')])

  render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  )

  expect(await screen.findByText('Neon Rebellion')).toBeInTheDocument()
  expect(screen.getByText('Cyber Vale')).toBeInTheDocument()
})
