import { afterEach, expect, test, vi } from 'vitest'
import { createProject, generateReferenceImage, getProviderModels, getProviders, updateProject } from './api'

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

test('generateReferenceImage posts payload to variant endpoint', async () => {
  const fn = vi.fn().mockResolvedValue(ok([{ id: 9, variant_id: 3, path: 'x.png' }]))
  vi.stubGlobal('fetch', fn)

  await generateReferenceImage(3, { prompt: 'héroe', count: 2, model: 'gemini-3-pro-image' })

  const [url, init] = fn.mock.calls[0] as [string, RequestInit]
  expect(String(url)).toContain('/api/v1/variants/3/images/generate')
  expect(init.method).toBe('POST')
  expect(init.body).toContain('héroe')
  expect(init.body).toContain('gemini-3-pro-image')
})

test('getProviders parses catalog', async () => {
  const fn = vi.fn().mockResolvedValue(
    ok({
      providers: {
        llm: [{ name: 'ollama', configured: true }],
        image: [{ name: 'gemini', configured: false }],
        video: [{ name: 'mock', configured: true }, { name: 'omni', configured: false }],
        tts: [{ name: 'edge', configured: true }],
      },
    }),
  )
  vi.stubGlobal('fetch', fn)

  const catalog = await getProviders()

  expect(catalog.video.map((o) => o.name)).toEqual(['mock', 'omni'])
  expect(catalog.video.find((o) => o.name === 'mock')?.configured).toBe(true)
  expect(catalog.image[0].configured).toBe(false)
})

test('updateProject patches settings', async () => {
  const fn = vi.fn().mockResolvedValue(ok({ id: 1 }))
  vi.stubGlobal('fetch', fn)

  await updateProject(1, { settings: { video_provider: 'omni' } })

  const [url, init] = fn.mock.calls[0] as [string, RequestInit]
  expect(String(url)).toContain('/api/v1/projects/1')
  expect(init.method).toBe('PATCH')
  expect(init.body).toContain('video_provider')
  expect(init.body).toContain('omni')
})

test('getProviderModels fetches models for provider', async () => {
  const fn = vi.fn().mockResolvedValue(
    ok({ models: [{ id: 'fal-ai/flux/dev', name: 'Flux Dev', description: 'x' }] }),
  )
  vi.stubGlobal('fetch', fn)

  const models = await getProviderModels('image', 'fal')

  const [url] = fn.mock.calls[0] as [string, RequestInit]
  expect(String(url)).toContain('/api/v1/providers/image/fal/models')
  expect(models[0].id).toBe('fal-ai/flux/dev')
})
