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
  dialogue_lines: DialogueLine[]
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
