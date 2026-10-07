import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'
import Stats from './Stats'
import { getStats, listProjects } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getStats: vi.fn(),
  listProjects: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listProjects).mockResolvedValue([
    {
      id: 1,
      name: 'Neon Rebellion',
      synopsis: '',
      video_style: '',
      aspect_ratio: '16:9',
      status: 'draft',
      settings: {},
      created_at: '',
      updated_at: '',
    },
  ])
  vi.mocked(getStats).mockResolvedValue({
    calls: [
      {
        id: 1,
        project_id: 1,
        job_id: 2,
        kind: 'llm',
        provider: 'openai',
        model: 'gpt-4o-mini',
        status: 'ok',
        duration_ms: 1500,
        input_tokens: 1000,
        output_tokens: 500,
        units: 0,
        cost_usd: 0.0005,
        error: null,
        created_at: '2026-10-04T10:00:00',
      },
    ],
    totals: {
      count: 1,
      cost_usd: 0.0005,
      input_tokens: 1000,
      output_tokens: 500,
      duration_ms: 1500,
    },
  })
})

function renderStats() {
  return render(
    <MemoryRouter>
      <Stats />
    </MemoryRouter>,
  )
}

test('shows totals and the request rows', async () => {
  renderStats()

  expect(await screen.findByText('gpt-4o-mini')).toBeInTheDocument()
  expect(screen.getByText('openai')).toBeInTheDocument()
  expect(screen.getAllByText('$0.0005').length).toBeGreaterThan(0)
  expect(screen.getAllByText('1.5 s').length).toBeGreaterThan(0)
})

test('shows a project filter with the projects', async () => {
  renderStats()

  expect(await screen.findByRole('combobox', { name: 'Proyecto' })).toBeInTheDocument()
  expect(await screen.findByText('Neon Rebellion')).toBeInTheDocument()
})
