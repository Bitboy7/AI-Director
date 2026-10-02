import type {
  Episode,
  Fragment,
  Job,
  Project,
  Resource,
  ResourceType,
} from '@/types'

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      // ignore parse errors
    }
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function listProjects(): Promise<Project[]> {
  return request('/projects')
}

export async function createProject(
  name: string,
  synopsis: string,
  video_style: string,
  aspect_ratio: string,
): Promise<Project> {
  return request('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, synopsis, video_style, aspect_ratio }),
  })
}

export async function getProject(id: number): Promise<Project> {
  return request(`/projects/${id}`)
}

export async function deleteProject(id: number): Promise<void> {
  return request(`/projects/${id}`, { method: 'DELETE' })
}

export async function generateScript(
  projectId: number,
  payload: {
    synopsis: string
    video_style?: string
    aspect_ratio?: string
    num_episodes?: number
    episode_duration_seconds?: number
    language?: string
  },
): Promise<Job> {
  return request(`/projects/${projectId}/generate-script`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function generateResources(projectId: number): Promise<Job> {
  return request(`/projects/${projectId}/generate-resources`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function listEpisodes(projectId: number): Promise<Episode[]> {
  return request(`/projects/${projectId}/episodes`)
}

export async function listFragments(episodeId: number): Promise<Fragment[]> {
  return request(`/episodes/${episodeId}/fragments`)
}

export async function updateFragment(
  id: number,
  patch: Partial<Fragment>,
): Promise<Fragment> {
  return request(`/fragments/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function listResources(projectId: number): Promise<Resource[]> {
  return request(`/projects/${projectId}/resources`)
}

export async function createResource(
  projectId: number,
  type: ResourceType,
  name: string,
): Promise<Resource> {
  return request(`/projects/${projectId}/resources`, {
    method: 'POST',
    body: JSON.stringify({ type, name }),
  })
}

export async function createVariant(
  resourceId: number,
  payload: {
    name: string
    description?: string
    episodes?: number[]
    voice?: Record<string, unknown>
  },
): Promise<Resource['variants'][number]> {
  return request(`/resources/${resourceId}/variants`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function uploadReferenceImage(
  variantId: number,
  file: File,
): Promise<Resource['variants'][number]['reference_images'][number]> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${BASE}/variants/${variantId}/images`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) throw new Error('falló la subida de imagen')
  return response.json()
}

export async function generateEpisode(
  episodeId: number,
  subtitle_burn?: boolean,
): Promise<{ video_job_ids: number[]; assembly_job_id: number }> {
  return request(`/episodes/${episodeId}/generate`, {
    method: 'POST',
    body: JSON.stringify({ subtitle_burn }),
  })
}

export async function generateFragment(fragmentId: number): Promise<Job> {
  return request(`/fragments/${fragmentId}/generate`, { method: 'POST' })
}

export async function getJob(jobId: number): Promise<Job> {
  return request(`/jobs/${jobId}`)
}

export async function cancelJob(jobId: number): Promise<Job> {
  return request(`/jobs/${jobId}/cancel`, { method: 'POST' })
}

export function subscribeJob(jobId: number, onEvent: (job: Job) => void): () => void {
  const source = new EventSource(`${BASE}/jobs/${jobId}/events`)
  source.onmessage = (event) => {
    try {
      onEvent(JSON.parse(event.data) as Job)
    } catch {
      // ignore malformed events
    }
  }
  source.onerror = () => source.close()
  return () => source.close()
}

export function assetUrl(path: string): string {
  return `${BASE}/assets/${path}`
}

export interface VerifyResult {
  status: 'ok' | 'error' | 'unavailable' | 'not_needed' | 'mock'
  detail?: string
}

export async function getCredentials(): Promise<Record<string, Record<string, string>>> {
  const data = await request<{ providers: Record<string, Record<string, string>> }>(
    '/settings/credentials',
  )
  return data.providers
}

export async function putCredentials(
  provider: string,
  credentials: Record<string, string>,
): Promise<void> {
  await request(`/settings/credentials/${provider}`, {
    method: 'PUT',
    body: JSON.stringify({ credentials }),
  })
}

export async function deleteCredential(provider: string, key: string): Promise<void> {
  await request(`/settings/credentials/${provider}/${key}`, { method: 'DELETE' })
}

export async function verifyCredential(provider: string): Promise<VerifyResult> {
  return request(`/settings/credentials/${provider}/verify`, { method: 'POST' })
}

export async function setPhaseCompleted(
  projectId: number,
  phase: number,
  completed: boolean,
): Promise<Project> {
  return request(`/projects/${projectId}/phases/${phase}`, {
    method: 'PUT',
    body: JSON.stringify({ completed }),
  })
}
