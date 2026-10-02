import { act, render, screen } from '@testing-library/react'
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
  type: 'video_gen',
  status: 'running',
  progress: 50,
  payload: {},
  result: {},
  error: null,
  parent_id: null,
  project_id: 1,
  created_at: '',
  updated_at: '',
}

const doneJob: Job = { ...runningJob, status: 'succeeded', progress: 100 }

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
})

test('polls until succeeded and shows progress', async () => {
  vi.mocked(getJob).mockResolvedValueOnce(runningJob).mockResolvedValue(doneJob)

  render(<JobProgress jobId={1} />)

  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
  expect(screen.getByText(/Procesando/)).toBeInTheDocument()
  expect(screen.getByText('50%')).toBeInTheDocument()

  await act(async () => {
    await vi.advanceTimersByTimeAsync(1100)
  })
  expect(screen.getByText(/Completado/)).toBeInTheDocument()
  expect(getJob).toHaveBeenCalledWith(1)
  vi.useRealTimers()
})

test('shows error message', async () => {
  const failed: Job = { ...runningJob, status: 'failed', error: 'proveedor caído' }
  vi.mocked(getJob).mockResolvedValue(failed)

  render(<JobProgress jobId={2} />)

  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
  expect(screen.getByText(/proveedor caído/)).toBeInTheDocument()
  vi.useRealTimers()
})
