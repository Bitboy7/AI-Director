import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import JobProgress from './JobProgress'
import { getJob } from '@/lib/api'
import type { Job } from '@/types'

vi.mock('@/lib/api', () => ({
  getJob: vi.fn(),
  cancelJob: vi.fn(),
}))

const runningJob: Job = {
  id: 1,
  type: 'script_gen',
  status: 'running',
  progress: 23,
  payload: {},
  result: {},
  error: null,
  parent_id: null,
  project_id: 1,
  created_at: '',
  updated_at: '',
}

beforeEach(() => {
  vi.clearAllMocks()
})

test('shows percentage and resource hint while running', async () => {
  vi.mocked(getJob).mockResolvedValue(runningJob)

  render(<JobProgress jobId={1} />)

  expect(await screen.findByText('23%')).toBeInTheDocument()
  expect(await screen.findByText(/progreso estimado/i)).toBeInTheDocument()
})

test('calls onComplete once when the job succeeds', async () => {
  const succeeded: Job = { ...runningJob, status: 'succeeded', progress: 100 }
  vi.mocked(getJob).mockResolvedValue(succeeded)
  const onComplete = vi.fn()

  render(<JobProgress jobId={1} onComplete={onComplete} />)

  await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1))
  expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({ status: 'succeeded' }))
})