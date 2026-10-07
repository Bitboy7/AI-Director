import type {
  Episode,
  Fragment,
  Job,
  Project,
  ReferenceImage,
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

export async function updateProject(id: number, patch: Partial<Project>): Promise<Project> {
  return request(`/projects/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export interface ProviderOption {
  name: string
  configured: boolean
}

export interface ProviderCatalog {
  llm: ProviderOption[]
  image: ProviderOption[]
  video: ProviderOption[]
  tts: ProviderOption[]
}

export interface ModelPricing {
  unit: 'second' | 'image' | '1m_tokens' | string
  usd?: number
  input?: number
  output?: number
}

export interface ProviderModel {
  id: string
  name: string
  description: string
  pricing?: ModelPricing | null
}

export interface StyleOption {
  id: string
  label: string
}

export const DEFAULT_STYLE_ID = 'anime'

export async function getStyles(): Promise<StyleOption[]> {
  const data = await request<{ styles: StyleOption[] }>('/styles')
  return data.styles
}

export async function getProviders(): Promise<ProviderCatalog> {
  const data = await request<{ providers: ProviderCatalog }>('/providers')
  return data.providers
}

export async function getProviderModels(
  kind: 'llm' | 'image' | 'video' | 'tts',
  provider: string,
): Promise<ProviderModel[]> {
  const data = await request<{ models: ProviderModel[] }>(
    `/providers/${kind}/${provider}/models`,
  )
  return data.models
}

export interface ResolutionOption {
  label: string
  value?: string
}

export async function getResolutions(
  kind: 'llm' | 'image' | 'video' | 'tts',
  provider: string,
  params: { model?: string; aspect?: string } = {},
): Promise<ResolutionOption[]> {
  const search = new URLSearchParams()
  if (params.aspect) search.set('aspect', params.aspect)
  if (params.model) search.set('model', params.model)
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const data = await request<{ resolutions: ResolutionOption[] }>(
    `/providers/${kind}/${provider}/resolutions${suffix}`,
  )
  return data.resolutions
}

export interface VoiceOption {
  short_name: string
  locale: string
  gender: string
  friendly_name: string
}

export async function getVoices(locale?: string): Promise<VoiceOption[]> {
  const suffix = locale ? `?locale=${encodeURIComponent(locale)}` : ''
  const data = await request<{ voices: VoiceOption[] }>(`/voices${suffix}`)
  return data.voices
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

export interface ScriptResource {
  name: string
  description: string
  tags: string[]
}

export interface ScriptDialogue {
  character: string
  text: string
}

export interface ScriptShot {
  shot_number: number
  time_place: string
  cast: string[]
  action: string
  dialogues: ScriptDialogue[]
}

export interface ScriptEpisodeDraft {
  number: number
  title: string
  shots: ScriptShot[]
}

export interface ScriptDraft {
  synopsis: string
  characters: ScriptResource[]
  scenes: ScriptResource[]
  props: ScriptResource[]
  episodes: ScriptEpisodeDraft[]
}

export async function getScriptDraft(
  projectId: number,
): Promise<{ draft: ScriptDraft | null; confirmed: boolean }> {
  return request(`/projects/${projectId}/script-draft`)
}

export async function confirmScript(projectId: number): Promise<Project> {
  return request(`/projects/${projectId}/confirm-script`, { method: 'POST' })
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

export async function createFragment(
  episodeId: number,
  payload: {
    shot_number: number
    time_place?: string
    prompt_video?: string
    duration?: number
    cast?: unknown[]
  },
): Promise<Fragment> {
  return request(`/episodes/${episodeId}/fragments`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteFragment(fragmentId: number): Promise<void> {
  return request(`/fragments/${fragmentId}`, { method: 'DELETE' })
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

export async function updateResource(
  id: number,
  patch: { name?: string; profile?: Record<string, unknown>; type?: ResourceType },
): Promise<Resource> {
  return request(`/resources/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function updateVariant(
  id: number,
  patch: { name?: string; description?: string; voice?: Record<string, unknown> },
): Promise<Resource['variants'][number]> {
  return request(`/variants/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
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

export async function generateReferenceImage(
  variantId: number,
  payload: { prompt?: string; count?: number; style?: string; model?: string },
): Promise<ReferenceImage[]> {
  return request(`/variants/${variantId}/images/generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function generateResourceImages(
  projectId: number,
  payload: { resource_ids: number[]; provider?: string; model?: string },
): Promise<Job> {
  return request(`/projects/${projectId}/resources/generate-images`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
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

export async function assembleEpisode(
  episodeId: number,
  subtitle_burn?: boolean,
): Promise<Job> {
  return request(`/episodes/${episodeId}/assemble`, {
    method: 'POST',
    body: JSON.stringify({ subtitle_burn }),
  })
}

export function exportEpisodeUrl(episodeId: number): string {
  return `${BASE}/episodes/${episodeId}/final?download=1`
}

export function episodeFinalUrl(episodeId: number): string {
  return `${BASE}/episodes/${episodeId}/final`
}

export function projectCoverUrl(projectId: number): string {
  return `${BASE}/projects/${projectId}/cover`
}

export interface CostEstimateEpisode {
  episode_id: number
  number: number
  title: string
  fragments: number
  seconds: number
  cost_usd: number
}

export interface CostEstimate {
  episodes: CostEstimateEpisode[]
  total: { fragments: number; seconds: number; cost_usd: number }
}

export async function getCostEstimate(projectId: number): Promise<CostEstimate> {
  return request(`/projects/${projectId}/cost-estimate`)
}

export async function selectFragmentVideo(
  fragmentId: number,
  videoId: number,
): Promise<import('@/types').Fragment> {
  return request(`/fragments/${fragmentId}/videos/${videoId}/select`, { method: 'POST' })
}

export async function generateStoryboards(
  projectId: number,
  payload: { episode_ids?: number[] } = {},
): Promise<Job> {
  return request(`/projects/${projectId}/storyboards`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateStoryboardPanel(
  panelId: number,
  patch: Partial<import('@/types').StoryboardPanel>,
): Promise<import('@/types').StoryboardPanel> {
  return request(`/storyboard-panels/${panelId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function createStoryboardPanel(
  fragmentId: number,
  payload: { title?: string; start_seconds?: number; end_seconds?: number; prompt?: string },
): Promise<import('@/types').StoryboardPanel> {
  return request(`/fragments/${fragmentId}/storyboard-panels`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteStoryboardPanel(panelId: number): Promise<void> {
  return request(`/storyboard-panels/${panelId}`, { method: 'DELETE' })
}

export async function generateFragmentReference(
  fragmentId: number,
): Promise<import('@/types').FragmentReferenceImage> {
  return request(`/fragments/${fragmentId}/reference-images/generate`, { method: 'POST' })
}

export async function uploadFragmentReference(
  fragmentId: number,
  file: File,
): Promise<import('@/types').FragmentReferenceImage> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${BASE}/fragments/${fragmentId}/reference-images`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) throw new Error('falló la subida de la imagen de referencia')
  return response.json()
}

export async function getJob(jobId: number): Promise<Job> {
  return request(`/jobs/${jobId}`)
}

export async function listJobs(projectId?: number): Promise<Job[]> {
  const suffix = projectId != null ? `?project_id=${projectId}` : ''
  return request(`/jobs${suffix}`)
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

export async function getStats(params: {
  project_id?: number
  kind?: string
  limit?: number
} = {}): Promise<import('@/types').StatsResponse> {
  const search = new URLSearchParams()
  if (params.project_id != null) search.set('project_id', String(params.project_id))
  if (params.kind) search.set('kind', params.kind)
  if (params.limit != null) search.set('limit', String(params.limit))
  const suffix = search.toString() ? `?${search.toString()}` : ''
  return request(`/stats${suffix}`)
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
