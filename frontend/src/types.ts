export type ResourceType = 'character' | 'scene' | 'prop'
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface Project {
  id: number
  name: string
  synopsis: string
  video_style: string
  aspect_ratio: string
  status: string
  settings: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DialogueLine {
  id: number
  fragment_id: number
  character_variant_id: number | null
  text: string
  order: number
}

export interface CastEntry {
  name: string
  variant_id?: number | null
}

export interface StoryboardPanel {
  id: number
  fragment_id: number
  order: number
  title: string
  start_seconds: number
  end_seconds: number
  prompt: string
}

export interface FragmentReferenceImage {
  id: number
  fragment_id: number
  path: string
  origin: 'uploaded' | 'generated'
}

export interface FragmentVideo {
  id: number
  fragment_id: number
  path: string
  provider: string
  model: string
  resolution: string | null
  cost_usd: number
  created_at: string
}

export interface Fragment {
  id: number
  episode_id: number
  shot_number: number
  time_place: string
  cast: CastEntry[]
  prompt_video: string
  duration: number
  status: string
  video_path: string | null
  video_provider: string | null
  video_model: string | null
  resolution: string | null
  cost_usd: number
  dialogue_lines: DialogueLine[]
  storyboard: StoryboardPanel[]
  reference_images: FragmentReferenceImage[]
  videos: FragmentVideo[]
}

export interface Episode {
  id: number
  project_id: number
  number: number
  title: string
  script: Record<string, unknown>
  status: string
  fragments: Fragment[]
}

export interface ReferenceImage {
  id: number
  variant_id: number
  path: string
  origin: 'uploaded' | 'generated'
  kind: string
}

export interface ResourceVariant {
  id: number
  resource_id: number
  name: string
  description: string
  episodes: number[]
  image_model: string
  image_style: string
  voice: Record<string, unknown>
  reference_images: ReferenceImage[]
}

export interface Resource {
  id: number
  project_id: number
  type: ResourceType
  name: string
  profile: Record<string, unknown>
  variants: ResourceVariant[]
}

export interface Job {
  id: number
  type: string
  status: JobStatus
  progress: number
  payload: Record<string, unknown>
  result: Record<string, unknown>
  error: string | null
  parent_id: number | null
  project_id: number | null
  created_at: string
  updated_at: string
}

export interface ApiCall {
  id: number
  project_id: number | null
  job_id: number | null
  kind: string
  provider: string
  model: string
  status: string
  duration_ms: number
  input_tokens: number
  output_tokens: number
  units: number
  cost_usd: number
  error: string | null
  created_at: string
}

export interface StatsTotals {
  count: number
  cost_usd: number
  input_tokens: number
  output_tokens: number
  duration_ms: number
}

export interface StatsResponse {
  calls: ApiCall[]
  totals: StatsTotals
}
