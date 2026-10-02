import { afterEach, expect, test, vi } from 'vitest'
import { createProject } from './api'

function ok(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('createProject posts payload', async () => {
  const fn = vi.fn().mockResolvedValue(ok({ id: 1 }))
  vi.stubGlobal('fetch', fn)

  await createProject('Neon Rebellion', 'syn', 'cyberpunk', '16:9')

  expect(fn).toHaveBeenCalledTimes(1)
  const [url, init] = fn.mock.calls[0] as [string, RequestInit]
  expect(String(url)).toContain('/api/v1/projects')
  expect(init.method).toBe('POST')
  expect(init.body).toContain('Neon Rebellion')
  expect(init.body).toContain('cyberpunk')
})
