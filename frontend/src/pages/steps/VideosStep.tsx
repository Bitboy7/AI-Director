import { useEffect, useState } from 'react'
import {
  Check,
  Clock,
  Coins,
  Download,
  Film,
  ImageIcon,
  LayoutGrid,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react'
import JobProgress from '@/components/JobProgress'
import MentionTextarea from '@/components/MentionTextarea'
import ProviderSelector from '@/components/ProviderSelector'
import VideoPlayer from '@/components/VideoPlayer'
import { RenderCurtain, RenderFlash } from '@/components/RenderCurtain'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Stamp, DoneCheck } from '@/components/stamp'
import { cn } from '@/lib/utils'
import { formatCost, formatDuration } from '@/lib/format'
import {
  assembleEpisode,
  assetUrl,
  createFragment,
  createStoryboardPanel,
  deleteFragment,
  deleteStoryboardPanel,
  generateEpisode,
  generateFragment,
  generateFragmentReference,
  generateStoryboards,
  episodeFinalUrl,
  exportEpisodeUrl,
  getCostEstimate,
  getProviders,
  listEpisodes,
  listJobs,
  listResources,
  selectFragmentVideo,
  updateFragment,
  updateProject,
  updateStoryboardPanel,
  uploadFragmentReference,
  type CostEstimate,
  type ProviderOption,
} from '@/lib/api'
import type { Episode, Fragment, Job, Project, Resource, StoryboardPanel } from '@/types'

interface Props {
  project: Project
  onProjectUpdated?: () => void
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente',
  generated: 'Generado',
}

const CHAPTER_BUTTON =
  'h-9 gap-2 rounded-xl border border-border/70 bg-gradient-to-b from-muted/50 to-muted/10 px-3.5 text-[0.8rem] font-medium text-foreground/90 shadow-[inset_0_1px_0_0_color-mix(in_oklch,var(--foreground)_10%,transparent),0_10px_24px_-18px_rgba(0,0,0,0.7)] transition-all duration-200 hover:-translate-y-0.5 hover:border-pencil/60 hover:from-muted/70 hover:to-muted/20 hover:text-foreground hover:shadow-[inset_0_1px_0_0_color-mix(in_oklch,var(--foreground)_14%,transparent),0_16px_32px_-18px_color-mix(in_oklch,var(--pencil)_45%,transparent)] active:translate-y-0 disabled:hover:translate-y-0'

const CHAPTER_BUTTON_PRIMARY =
  'h-9 gap-2 rounded-xl border border-pencil/40 bg-gradient-to-b from-pencil to-[color-mix(in_oklch,var(--pencil)_82%,black)] px-3.5 text-[0.8rem] font-semibold text-primary-foreground shadow-[inset_0_1px_0_0_color-mix(in_oklch,white_28%,transparent),0_14px_30px_-14px_color-mix(in_oklch,var(--pencil)_60%,transparent)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[inset_0_1px_0_0_color-mix(in_oklch,white_32%,transparent),0_20px_40px_-16px_color-mix(in_oklch,var(--pencil)_70%,transparent)] active:translate-y-0'

function episodeSeconds(episode: Episode) {
  return episode.fragments.reduce((acc, fragment) => acc + (fragment.duration ?? 0), 0)
}

function EpisodeTabs({
  episodes,
  selectedId,
  onSelect,
}: {
  episodes: Episode[]
  selectedId: string
  onSelect: (value: string) => void
}) {
  return (
    <div
      role="tablist"
      aria-label="Episodios"
      className="flex gap-2.5 overflow-x-auto pb-1"
    >
      {episodes.map((episode) => {
        const total = episode.fragments.length
        const done = episode.fragments.filter((fragment) => fragment.status === 'generated').length
        const complete = total > 0 && done === total
        const active = String(episode.id) === selectedId
        const progress = total > 0 ? (done / total) * 100 : 0
        return (
          <button
            key={episode.id}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onSelect(String(episode.id))}
            className={cn(
              'group relative flex min-w-[12rem] shrink-0 flex-col gap-2 overflow-hidden rounded-xl border bg-card px-3 py-2.5 text-left transition-all duration-300',
              active
                ? 'border-pencil/70 bg-pencil/10 shadow-[0_0_0_1px_color-mix(in_oklch,var(--pencil)_70%,transparent),0_14px_32px_-18px_color-mix(in_oklch,var(--pencil)_45%,transparent)]'
                : 'border-border hover:border-border/80 hover:bg-muted/30',
            )}
          >
            <span className="flex items-center justify-between gap-2">
              <span
                className={cn(
                  'timecode text-lg leading-none font-semibold',
                  active ? 'text-pencil' : 'text-foreground/85',
                )}
              >
                {String(episode.number).padStart(2, '0')}
              </span>
              {complete ? (
                <DoneCheck />
              ) : (
                <span className="timecode text-xs text-muted-foreground">
                  {done}/{total}
                </span>
              )}
            </span>
            <span className="truncate text-sm leading-tight font-medium">
              {episode.title || `Capítulo ${episode.number}`}
            </span>
            <span className="flex items-center justify-between gap-2">
              <span className="slug">Cap. {episode.number}</span>
              <span className="timecode text-xs text-muted-foreground">
                {formatDuration(episodeSeconds(episode))}
              </span>
            </span>
            <span className="absolute inset-x-0 bottom-0 h-0.5 bg-border/60">
              <span
                className={cn(
                  'block h-full bg-pencil transition-[width] duration-500',
                  active ? 'opacity-100' : 'opacity-50',
                )}
                style={{ width: `${progress}%` }}
              />
            </span>
          </button>
        )
      })}
    </div>
  )
}

const MAX_PANELS = 4

function StoryboardPanels({
  fragmentId,
  panels,
  resources,
  onChanged,
}: {
  fragmentId: number
  panels: StoryboardPanel[]
  resources: Resource[]
  onChanged: () => void
}) {
  const add = async () => {
    const last = panels[panels.length - 1]
    await createStoryboardPanel(fragmentId, {
      title: '',
      start_seconds: last ? last.end_seconds : 0,
      end_seconds: last ? last.end_seconds + 3 : 3,
      prompt: '',
    })
    onChanged()
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="slug">Storyboard</p>
        <span className="text-[0.6875rem] text-muted-foreground">
          Escribe <span className="text-pencil">@</span> para referenciar recursos
        </span>
      </div>
      {panels.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Sin storyboard. Genera con IA o añade uno manualmente.
        </p>
      ) : (
        panels.map((panel) => (
          <PanelRow key={panel.id} panel={panel} resources={resources} onChanged={onChanged} />
        ))
      )}
      <Button
        variant="outline"
        size="sm"
        onClick={() => void add()}
        disabled={panels.length >= MAX_PANELS}
      >
        <Plus />
        Añadir storyboard ({panels.length}/{MAX_PANELS})
      </Button>
    </div>
  )
}

function PanelRow({
  panel,
  resources,
  onChanged,
}: {
  panel: StoryboardPanel
  resources: Resource[]
  onChanged: () => void
}) {
  const [title, setTitle] = useState(panel.title)
  const [start, setStart] = useState(panel.start_seconds)
  const [end, setEnd] = useState(panel.end_seconds)
  const [prompt, setPrompt] = useState(panel.prompt)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setTitle(panel.title)
    setStart(panel.start_seconds)
    setEnd(panel.end_seconds)
    setPrompt(panel.prompt)
  }, [panel])

  const save = async () => {
    const patch: Partial<StoryboardPanel> = {}
    if (title !== panel.title) patch.title = title
    if (start !== panel.start_seconds) patch.start_seconds = start
    if (end !== panel.end_seconds) patch.end_seconds = end
    if (prompt !== panel.prompt) patch.prompt = prompt
    if (Object.keys(patch).length === 0) return
    setSaving(true)
    try {
      await updateStoryboardPanel(panel.id, patch)
      onChanged()
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    await deleteStoryboardPanel(panel.id)
    onChanged()
  }

  return (
    <div className="rounded-lg border border-border bg-background/40 p-2.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <Input
          type="number"
          value={start}
          onChange={(event) => setStart(Number(event.target.value))}
          onBlur={() => void save()}
          aria-label={`inicio-${panel.id}`}
          className="h-7 w-14 text-xs"
        />
        <span className="text-xs text-muted-foreground">-</span>
        <Input
          type="number"
          value={end}
          onChange={(event) => setEnd(Number(event.target.value))}
          onBlur={() => void save()}
          aria-label={`fin-${panel.id}`}
          className="h-7 w-14 text-xs"
        />
        <span className="text-xs text-muted-foreground">s</span>
        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          onBlur={() => void save()}
          placeholder="Título del panel"
          aria-label={`titulo-${panel.id}`}
          className="h-7 min-w-32 flex-1 text-xs"
        />
        {saving && <span className="slug">guardando…</span>}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => void remove()}
          aria-label={`Eliminar panel ${panel.id}`}
          className="text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>
      <div className="mt-1.5">
        <MentionTextarea
          value={prompt}
          onChange={setPrompt}
          onBlur={() => void save()}
          resources={resources}
          rows={2}
          className="text-xs"
          ariaLabel={`panel-${panel.id}`}
        />
      </div>
    </div>
  )
}

function FragmentReference({
  fragment,
  onChanged,
}: {
  fragment: Fragment
  onChanged: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const image = fragment.reference_images[fragment.reference_images.length - 1]

  const generate = async () => {
    setBusy(true)
    setError(null)
    try {
      await generateFragmentReference(fragment.id)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar la imagen de referencia')
    } finally {
      setBusy(false)
    }
  }

  const upload = async (file: File) => {
    setBusy(true)
    setError(null)
    try {
      await uploadFragmentReference(fragment.id, file)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al subir la imagen')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2">
      <p className="slug">Referencia</p>
      <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-border bg-muted">
        {image ? (
          <img
            src={assetUrl(image.path)}
            alt={`referencia ${fragment.shot_number}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <ImageIcon className="size-6 text-muted-foreground/60" />
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => void generate()} disabled={busy}>
          {busy ? 'Generando…' : 'Generar referencia'}
        </Button>
        <label className="inline-flex cursor-pointer items-center gap-1 text-xs text-muted-foreground">
          <Upload className="size-3.5" />
          Subir imagen
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void upload(file)
            }}
          />
        </label>
      </div>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  )
}

interface FragmentDefaults {
  provider: string
  model: string
  resolution: string | null
}

function FragmentFrame({
  fragment,
  episode,
  project,
  defaults,
  providers,
  resources,
  jobId,
  version,
  onGenerate,
  onGenerated,
  onChanged,
  onDelete,
  onSettingsChange,
}: {
  fragment: Fragment
  episode: Episode
  project: Project
  defaults: FragmentDefaults
  providers: ProviderOption[]
  resources: Resource[]
  jobId?: number
  version: number
  onGenerate: () => void
  onGenerated: () => void
  onChanged: () => void
  onDelete: () => void
  onSettingsChange: (patch: Partial<Fragment>) => void
}) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const handleSelect = async (videoId: number) => {
    await selectFragmentVideo(fragment.id, videoId)
    onChanged()
  }

  const overridesProvider = fragment.video_provider != null
  const effectiveProvider = fragment.video_provider ?? defaults.provider
  const effectiveModel = fragment.video_model ?? (overridesProvider ? '' : defaults.model)
  const effectiveResolution = fragment.resolution ?? defaults.resolution
  const inheritsSettings =
    fragment.video_provider == null && fragment.video_model == null && fragment.resolution == null

  return (
    <Card className="animate-frame-in overflow-hidden">
      <CardContent className="grid gap-5 lg:grid-cols-2">
        {/* Columna izquierda: segmento + storyboard */}
        <div className="space-y-3.5 lg:pr-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="timecode rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs font-semibold text-pencil">
                  Segmento {fragment.shot_number}
                </span>
                {fragment.status === 'generated' ? (
                  <DoneCheck />
                ) : (
                  <Stamp tone="muted">{STATUS_LABEL[fragment.status] ?? fragment.status}</Stamp>
                )}
              </div>
              <h3 className="mt-2 truncate text-base font-semibold tracking-tight">
                {fragment.time_place || `Plano ${fragment.shot_number}`}
              </h3>
              <p className="slug mt-1 flex items-center gap-1.5">
                <Clock className="size-3" />
                Duración {formatDuration(fragment.duration)} · usa{' '}
                <span className="text-pencil">@</span> para referenciar
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {fragment.cost_usd > 0 && (
                <Stamp tone="pencil" className="animate-none">
                  <Coins className="size-2.5" />
                  {formatCost(fragment.cost_usd)}
                </Stamp>
              )}
              {fragment.video_path && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Regenerar plano ${episode.number}-${fragment.shot_number}`}
                  title="Regenerar plano"
                  onClick={() => setConfirmOpen(true)}
                >
                  <RefreshCw />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Eliminar plano ${episode.number}-${fragment.shot_number}`}
                title="Eliminar plano"
                className="text-muted-foreground hover:text-destructive"
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 />
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-muted/10 p-3">
            <p className="slug mb-1.5">Generar un video a partir de estos storyboards</p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Configuración de escena para este clip:{' '}
              <span className="rounded bg-pencil/10 px-1.5 py-0.5 text-pencil">
                {fragment.prompt_video || '—'}
              </span>
            </p>
          </div>

          <div className="rounded-lg border border-border bg-muted/10 p-3">
            <StoryboardPanels
              fragmentId={fragment.id}
              panels={fragment.storyboard}
              resources={resources}
              onChanged={onChanged}
            />
          </div>
        </div>

        {/* Columna derecha: ajustes + clip/keyframe + historial */}
        <div className="space-y-3.5 lg:border-l lg:border-border lg:pl-5">
          <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-2 rounded-lg border border-border bg-muted/10 p-3">
            <ProviderSelector
              kind="video"
              label="Proveedor"
              value={effectiveProvider}
              onChange={(value) => onSettingsChange({ video_provider: value, video_model: null })}
              model={effectiveModel}
              onModelChange={(value) => onSettingsChange({ video_model: value })}
              resolution={effectiveResolution}
              onResolutionChange={(value) => onSettingsChange({ resolution: value })}
              aspect={project.aspect_ratio || '16:9'}
              durationSeconds={fragment.duration}
              providers={providers}
              dense
            />
            <div className="ml-auto flex items-center gap-1.5 pb-1">
              <span className="slug flex items-center gap-1.5 leading-none">
                {inheritsSettings ? (
                  <>
                    <span className="size-1.5 rounded-full bg-pencil/60" />
                    Hereda del proyecto
                  </>
                ) : (
                  <>
                    <span className="size-1.5 rounded-full bg-pencil" />
                    Ajuste propio
                  </>
                )}
              </span>
              {!inheritsSettings && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={`Restablecer ajustes del plano ${episode.number}-${fragment.shot_number}`}
                  title="Volver a heredar del proyecto"
                  onClick={() =>
                    onSettingsChange({
                      video_provider: null,
                      video_model: null,
                      resolution: null,
                    })
                  }
                >
                  <RotateCcw />
                </Button>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-muted/10 p-3">
            <div className="mb-2.5 flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <ImageIcon className="size-3.5" />
                {fragment.video_path ? 'Clip generado' : 'Sin clip generado'}
              </span>
              <Button
                size="sm"
                onClick={() => (fragment.video_path ? setConfirmOpen(true) : onGenerate())}
              >
                <Sparkles />
                Generar
              </Button>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1 overflow-hidden rounded-lg border border-border bg-black">
                {fragment.video_path ? (
                  <video
                    key={`${fragment.id}-${version}`}
                    controls
                    className="aspect-video w-full object-cover"
                    src={`${assetUrl(fragment.video_path)}?v=${version}`}
                  />
                ) : (
                  <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 bg-gradient-to-b from-muted/40 to-transparent">
                    <Film className="size-8 text-muted-foreground/50" />
                    <p className="slug">Sin render</p>
                  </div>
                )}
              </div>
              {fragment.videos.length > 0 && (
                <div className="shrink-0 space-y-2 sm:w-24">
                  <p className="slug">Historial</p>
                  {fragment.videos.map((video) => {
                    const selected = video.path === fragment.video_path
                    return (
                      <button
                        key={video.id}
                        type="button"
                        onClick={() => void handleSelect(video.id)}
                        aria-label={`Usar video ${video.id}`}
                        className={cn(
                          'relative block w-full overflow-hidden rounded-md border bg-black transition-colors',
                          selected
                            ? 'border-pencil ring-1 ring-pencil'
                            : 'border-border hover:border-border/80',
                        )}
                      >
                        <video
                          src={`${assetUrl(video.path)}#t=0.1`}
                          className="aspect-video w-full object-cover"
                          muted
                          preload="metadata"
                        />
                        {selected && (
                          <span className="absolute right-1 bottom-1 flex size-4 items-center justify-center rounded-full bg-pencil text-primary-foreground">
                            <Check className="size-3" />
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-muted/10 p-3">
            <FragmentReference fragment={fragment} onChanged={onChanged} />
          </div>
        </div>
      </CardContent>
      {jobId && (
        <div className="px-(--card-spacing) pb-(--card-spacing)">
          <JobProgress jobId={jobId} onComplete={onGenerated} />
        </div>
      )}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Regenerar plano {fragment.shot_number} · Capítulo {episode.number}
            </DialogTitle>
            <DialogDescription>
              Se reemplazará el video actual de este plano por uno nuevo. Úsalo para corregir
              idioma, encuadre de cámara o inconsistencias. Consume tiempo del proveedor de video.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" size="sm" />}>Cancelar</DialogClose>
            <Button
              size="sm"
              onClick={() => {
                setConfirmOpen(false)
                onGenerate()
              }}
            >
              <RefreshCw />
              Regenerar plano
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Eliminar plano {fragment.shot_number} · Capítulo {episode.number}
            </DialogTitle>
            <DialogDescription>
              Se eliminará este plano junto con su storyboard, imagen de referencia y videos
              generados. Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" size="sm" />}>Cancelar</DialogClose>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setDeleteOpen(false)
                onDelete()
              }}
            >
              <Trash2 />
              Eliminar plano
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export default function VideosStep({ project, onProjectUpdated }: Props) {
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [resources, setResources] = useState<Resource[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [assemblyJobId, setAssemblyJobId] = useState<number | null>(null)
  const [storyboardJobId, setStoryboardJobId] = useState<number | null>(null)
  const [fragmentJobIds, setFragmentJobIds] = useState<Record<number, number>>({})
  const [fragmentVersions, setFragmentVersions] = useState<Record<number, number>>({})
  const [renderJobId, setRenderJobId] = useState<number | null>(null)
  const [renderPhase, setRenderPhase] = useState<'idle' | 'rendering' | 'ready'>('idle')
  const [finalVersion, setFinalVersion] = useState(0)
  const [renderConfirmOpen, setRenderConfirmOpen] = useState(false)
  const [estimate, setEstimate] = useState<CostEstimate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [videoProvider, setVideoProvider] = useState(
    (project.settings.video_provider as string | undefined) ?? 'mock',
  )
  const [videoModel, setVideoModel] = useState(
    (project.settings.video_model as string | undefined) ?? '',
  )
  const [aspect, setAspect] = useState(project.aspect_ratio || '16:9')
  const [projectResolution, setProjectResolution] = useState(
    (project.settings.video_resolution as string | undefined) ?? null,
  )
  const [providers, setProviders] = useState<ProviderOption[]>([])

  const refresh = async () => setEpisodes(await listEpisodes(project.id))

  useEffect(() => {
    void refresh()
  }, [project.id])

  useEffect(() => {
    let cancelled = false
    void getProviders()
      .then((catalog) => {
        if (!cancelled) setProviders(catalog.video ?? [])
      })
      .catch(() => {
        if (!cancelled) setProviders([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void listResources(project.id).then(setResources).catch(() => setResources([]))
  }, [project.id])

  useEffect(() => {
    if (episodes.length === 0) return
    if (!selectedId || !episodes.some((episode) => String(episode.id) === selectedId)) {
      setSelectedId(String(episodes[0].id))
    }
  }, [episodes, selectedId])

  useEffect(() => {
    const ep = episodes.find((item) => String(item.id) === selectedId)
    if (!ep) return
    let cancelled = false
    void listJobs(project.id)
      .then((jobs) => {
        if (cancelled) return
        const active = jobs.find(
          (job) =>
            job.type === 'episode_assembly' &&
            (job.status === 'queued' || job.status === 'running') &&
            (job.payload as { episode_id?: number }).episode_id === ep.id,
        )
        if (active) {
          setAssemblyJobId(active.id)
          setRenderJobId(active.id)
          setRenderPhase('rendering')
        } else if (ep.status === 'assembled') {
          setRenderPhase('ready')
        } else {
          setRenderPhase('idle')
          setRenderJobId(null)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [selectedId, episodes, project.id])

  const handleAspectChange = async (value: string) => {
    setAspect(value)
    await updateProject(project.id, { aspect_ratio: value })
    onProjectUpdated?.()
  }

  const handleProviderChange = async (value: string) => {
    setVideoProvider(value)
    setVideoModel('')
    await updateProject(project.id, {
      settings: { ...project.settings, video_provider: value, video_model: '' },
    })
    onProjectUpdated?.()
  }

  const handleModelChange = async (value: string) => {
    setVideoModel(value)
    await updateProject(project.id, {
      settings: { ...project.settings, video_provider: videoProvider, video_model: value },
    })
    onProjectUpdated?.()
  }

  const handleResolutionChange = async (value: string) => {
    setProjectResolution(value)
    await updateProject(project.id, {
      settings: { ...project.settings, video_resolution: value },
    })
    onProjectUpdated?.()
  }

  const handleFragmentSettingsChange = async (fragmentId: number, patch: Partial<Fragment>) => {
    setError(null)
    try {
      await updateFragment(fragmentId, patch)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al guardar los ajustes del plano')
    }
  }

  const episode = episodes.find((ep) => String(ep.id) === selectedId) ?? null
  const hasAssembly = episode != null && assemblyJobId != null

  const handleGenerateEpisode = async () => {
    if (!episode) return
    setError(null)
    setRenderPhase('idle')
    setRenderJobId(null)
    try {
      const result = await generateEpisode(episode.id)
      setAssemblyJobId(result.assembly_job_id)
      setFragmentJobIds(
        Object.fromEntries(
          episode.fragments.map((fragment, index) => [fragment.id, result.video_job_ids[index]]),
        ),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar el episodio')
    }
  }

  const openRenderConfirm = async () => {
    setError(null)
    setEstimate(null)
    setRenderConfirmOpen(true)
    try {
      setEstimate(await getCostEstimate(project.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al estimar el coste')
    }
  }

  const handleGenerateAll = async () => {
    setRenderConfirmOpen(false)
    setError(null)
    setRenderPhase('idle')
    setRenderJobId(null)
    try {
      for (const ep of episodes) {
        if (!ep.fragments.some((fragment) => fragment.status !== 'generated')) continue
        const result = await generateEpisode(ep.id)
        if (String(ep.id) === selectedId) {
          setAssemblyJobId(result.assembly_job_id)
          setFragmentJobIds(
            Object.fromEntries(
              ep.fragments.map((fragment, index) => [fragment.id, result.video_job_ids[index]]),
            ),
          )
        }
      }
      void refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar los capítulos')
    }
  }

  const handleGenerateFragment = async (fragmentId: number) => {
    setError(null)
    setRenderPhase('idle')
    try {
      const job = await generateFragment(fragmentId)
      setFragmentJobIds((prev) => ({ ...prev, [fragmentId]: job.id }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar el fragmento')
    }
  }

  const handleFragmentGenerated = (fragmentId: number) => {
    setFragmentVersions((prev) => ({ ...prev, [fragmentId]: (prev[fragmentId] ?? 0) + 1 }))
    setRenderPhase('idle')
    void refresh()
  }

  const handleAddFragment = async () => {
    if (!episode) return
    setError(null)
    try {
      const nextShot =
        episode.fragments.reduce((max, fragment) => Math.max(max, fragment.shot_number), 0) + 1
      await createFragment(episode.id, {
        shot_number: nextShot,
        time_place: `Plano ${nextShot}`,
        duration: 10,
      })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al añadir el plano')
    }
  }

  const handleDeleteFragment = async (fragmentId: number) => {
    setError(null)
    try {
      await deleteFragment(fragmentId)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al eliminar el plano')
    }
  }

  const handleRender = async () => {
    if (!episode || !allGenerated) return
    setError(null)
    if (renderPhase === 'ready') {
      setFinalVersion((version) => version + 1)
      return
    }
    try {
      const job = await assembleEpisode(episode.id)
      setRenderJobId(job.id)
      setRenderPhase('rendering')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al renderizar el capítulo')
    }
  }

  const handleRerender = async () => {
    if (!episode || !allGenerated) return
    setError(null)
    try {
      const job = await assembleEpisode(episode.id)
      setRenderJobId(job.id)
      setRenderPhase('rendering')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al volver a renderizar el capítulo')
    }
  }

  const handleRenderComplete = (_job: Job) => {
    setRenderPhase('ready')
    setFinalVersion((version) => version + 1)
    void refresh()
  }

  const handleGenerateStoryboards = async () => {
    setError(null)
    try {
      const job = await generateStoryboards(project.id, {
        episode_ids: episode ? [episode.id] : undefined,
      })
      setStoryboardJobId(job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar los storyboards')
    }
  }

  const allGenerated =
    episode != null &&
    episode.fragments.length > 0 &&
    episode.fragments.every((fragment) => fragment.status === 'generated')

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          {episode && (
            <>
              <Button onClick={() => void openRenderConfirm()}>
                <Play />
                Generar episodio completo
              </Button>
              <Button variant="outline" onClick={() => void handleGenerateStoryboards()}>
                <LayoutGrid />
                Generar storyboards
              </Button>
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <ProviderSelector
            kind="video"
            value={videoProvider}
            label="Proveedor de video"
            onChange={(value) => void handleProviderChange(value)}
            model={videoModel}
            onModelChange={(value) => void handleModelChange(value)}
            resolution={projectResolution}
            onResolutionChange={(value) => void handleResolutionChange(value)}
            aspect={aspect}
            providers={providers}
          />
          <div
            role="group"
            aria-label="Relación de aspecto"
            className="flex items-center gap-0.5 rounded-lg border border-border p-0.5"
          >
            {(['16:9', '9:16'] as const).map((ratio) => (
              <button
                key={ratio}
                type="button"
                aria-pressed={aspect === ratio}
                onClick={() => void handleAspectChange(ratio)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                  aspect === ratio
                    ? 'bg-pencil/15 text-pencil'
                    : 'text-muted-foreground hover:bg-muted',
                )}
              >
                {ratio}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {hasAssembly && (
        <JobProgress
          key={`assembly-${assemblyJobId}`}
          jobId={assemblyJobId as number}
          onRetry={() => void handleGenerateEpisode()}
          onComplete={() => {
            setFinalVersion((value) => value + 1)
            setRenderPhase('ready')
            void refresh()
          }}
        />
      )}

      {storyboardJobId && (
        <JobProgress
          key={`storyboard-${storyboardJobId}`}
          jobId={storyboardJobId}
          onComplete={() => void refresh()}
        />
      )}

      {episodes.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <Film className="size-8 text-muted-foreground/50" />
            <div>
              <p className="text-sm font-medium">Sin episodios</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Confirma el guion en la fase anterior para generar los capítulos.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-5">
          <EpisodeTabs episodes={episodes} selectedId={selectedId} onSelect={setSelectedId} />

          {episode && (
            <div className="space-y-5">
              <Card className="overflow-hidden">
                <CardHeader>
                  <p className="slug">
                    Capítulo {episode.number} · Video final
                  </p>
                  <CardTitle>{episode.title || `Capítulo ${episode.number}`}</CardTitle>
                  <div
                    data-slot="card-action"
                    className="flex flex-wrap items-center gap-2 rounded-2xl border border-border/60 bg-background/40 p-1.5 backdrop-blur-sm"
                  >
                    {renderPhase === 'ready' ? (
                      <DoneCheck />
                    ) : (
                      <Stamp tone={allGenerated ? 'active' : 'muted'}>
                        {allGenerated ? 'Listo' : 'Ensamblaje'}
                      </Stamp>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className={renderPhase === 'ready' ? CHAPTER_BUTTON : CHAPTER_BUTTON_PRIMARY}
                      disabled={!allGenerated || renderPhase === 'rendering'}
                      onClick={() => void handleRender()}
                    >
                      {renderPhase === 'rendering' ? (
                        <>
                          <Loader2 className="animate-spin" />
                          Renderizando…
                        </>
                      ) : renderPhase === 'ready' ? (
                        <>
                          <Play />
                          Volver a reproducir
                        </>
                      ) : (
                        <>
                          <Sparkles />
                          Renderizar capítulo
                        </>
                      )}
                    </Button>
                    {renderPhase === 'ready' && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className={CHAPTER_BUTTON}
                        disabled={!allGenerated}
                        title={
                          allGenerated
                            ? 'Reensamblar el capítulo con los planos actuales'
                            : 'Genera todos los planos para volver a renderizar'
                        }
                        onClick={() => void handleRerender()}
                      >
                        <RefreshCw />
                        Volver a renderizar
                      </Button>
                    )}
                    {allGenerated && (
                      <a
                        href={exportEpisodeUrl(episode.id)}
                        download={`capitulo-${episode.number}.mp4`}
                        className={cn(buttonVariants({ variant: 'ghost' }), CHAPTER_BUTTON)}
                      >
                        <Download />
                        Exportar capítulo
                      </a>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="mx-auto max-w-3xl">
                    <div key={finalVersion} className="relative">
                      <div className={cn(renderPhase === 'ready' && 'animate-render-reveal')}>
                        <VideoPlayer
                          src={
                            renderPhase === 'ready'
                              ? `${episodeFinalUrl(episode.id)}?v=${finalVersion}`
                              : null
                          }
                          title={`${episode.title || `Capítulo ${episode.number}`} — final`}
                        />
                      </div>
                      {renderPhase === 'rendering' && (
                        <RenderCurtain
                          episodeNumber={episode.number}
                          title={episode.title || `Capítulo ${episode.number}`}
                        />
                      )}
                      {renderPhase === 'ready' && <RenderFlash key={`flash-${finalVersion}`} />}
                    </div>
                  </div>
                  {episode.fragments.length > 0 && !allGenerated && (
                    <p className="mx-auto max-w-3xl text-xs text-muted-foreground">
                      Genera todos los planos para poder renderizar el capítulo completo.
                    </p>
                  )}
                  {renderJobId != null && renderPhase === 'rendering' && (
                    <div className="mx-auto max-w-3xl">
                      <JobProgress
                        key={`render-${renderJobId}`}
                        jobId={renderJobId}
                        onComplete={handleRenderComplete}
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="slug">
                    Planos
                    <span className="timecode ml-2 text-muted-foreground">
                      {episode.fragments.length}
                    </span>
                  </p>
                  <Button variant="outline" size="sm" onClick={() => void handleAddFragment()}>
                    <Plus />
                    Añadir plano
                  </Button>
                </div>
                {episode.fragments.map((fragment) => (
                  <FragmentFrame
                    key={fragment.id}
                    fragment={fragment}
                    episode={episode}
                    project={project}
                    defaults={{
                      provider: videoProvider,
                      model: videoModel,
                      resolution: projectResolution,
                    }}
                    providers={providers}
                    resources={resources}
                    jobId={fragmentJobIds[fragment.id]}
                    version={fragmentVersions[fragment.id] ?? 0}
                    onGenerate={() => void handleGenerateFragment(fragment.id)}
                    onGenerated={() => handleFragmentGenerated(fragment.id)}
                    onChanged={() => void refresh()}
                    onDelete={() => void handleDeleteFragment(fragment.id)}
                    onSettingsChange={(patch) =>
                      void handleFragmentSettingsChange(fragment.id, patch)
                    }
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <Dialog open={renderConfirmOpen} onOpenChange={setRenderConfirmOpen}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Generar todos los capítulos</DialogTitle>
            <DialogDescription>
              Se generarán los planos pendientes de todos los capítulos y se ensamblará cada
              video final. Es un proceso largo y consume crédito del proveedor de video. El coste
              es una estimación según el proveedor, modelo y resolución seleccionados.
            </DialogDescription>
          </DialogHeader>
          {estimate ? (
            <div className="text-sm">
              <table className="w-full">
                <thead className="text-left text-xs text-muted-foreground">
                  <tr className="[&>th]:py-1">
                    <th>Capítulo</th>
                    <th className="text-right">Planos</th>
                    <th className="text-right">Seg.</th>
                    <th className="text-right">Coste</th>
                  </tr>
                </thead>
                <tbody>
                  {estimate.episodes.map((item) => (
                    <tr key={item.episode_id} className="border-t border-border/60">
                      <td className="max-w-52 truncate py-1">
                        {item.number}. {item.title}
                      </td>
                      <td className="timecode text-right">{item.fragments}</td>
                      <td className="timecode text-right">{item.seconds}</td>
                      <td className="timecode text-right">{formatCost(item.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-border font-medium">
                    <td className="py-1">Total</td>
                    <td className="timecode text-right">{estimate.total.fragments}</td>
                    <td className="timecode text-right">{estimate.total.seconds}</td>
                    <td className="timecode text-right">{formatCost(estimate.total.cost_usd)}</td>
                  </tr>
                </tfoot>
              </table>
              {estimate.total.fragments === 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  No hay planos pendientes de generar.
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Estimando coste…</p>
          )}
          <DialogFooter>
            <DialogClose render={<Button variant="outline" size="sm" />}>Cancelar</DialogClose>
            <Button
              size="sm"
              onClick={() => void handleGenerateAll()}
              disabled={!estimate || estimate.total.fragments === 0}
            >
              <Play />
              Generar todos los capítulos
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
