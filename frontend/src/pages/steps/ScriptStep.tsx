import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ChevronDown, ListTree, Sparkles } from 'lucide-react'
import JobProgress from '@/components/JobProgress'
import ProviderSelector from '@/components/ProviderSelector'
import StyleSelect from '@/components/StyleSelect'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { DoneCheck } from '@/components/stamp'
import { cn } from '@/lib/utils'
import { formatDuration } from '@/lib/format'
import {
  confirmScript,
  generateScript,
  getScriptDraft,
  getVoices,
  updateProject,
  DEFAULT_STYLE_ID,
  type ScriptDraft,
  type ScriptEpisodeDraft,
  type ScriptResource,
  type VoiceOption,
} from '@/lib/api'
import type { Project } from '@/types'

interface Props {
  project: Project
  onProjectUpdated?: () => void
}

export default function ScriptStep({ project, onProjectUpdated }: Props) {
  const [synopsis, setSynopsis] = useState(project.synopsis)
  const [videoStyle, setVideoStyle] = useState(project.video_style || DEFAULT_STYLE_ID)
  const [numEpisodes, setNumEpisodes] = useState(1)
  const [duration, setDuration] = useState(90)
  const [language, setLanguage] = useState((project.settings.language as string) || 'es-ES')
  const [voice, setVoice] = useState((project.settings.voice as string) || '')
  const [voices, setVoices] = useState<VoiceOption[]>([])
  const [jobId, setJobId] = useState<number | null>(null)
  const [draft, setDraft] = useState<ScriptDraft | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})
  const [error, setError] = useState<string | null>(null)
  const [llmProvider, setLlmProvider] = useState(
    (project.settings.llm_provider as string | undefined) ?? 'ollama',
  )
  const [llmModel, setLlmModel] = useState(
    (project.settings.llm_model as string | undefined) ?? '',
  )

  const refresh = async () => {
    const data = await getScriptDraft(project.id)
    setDraft(data.draft)
    setConfirmed(data.confirmed)
  }

  useEffect(() => {
    void refresh()
  }, [project.id])

  useEffect(() => {
    void getVoices()
      .then(setVoices)
      .catch(() => setVoices([]))
  }, [])

  const locales = useMemo(
    () => Array.from(new Set(voices.map((item) => item.locale))).sort(),
    [voices],
  )
  const localeVoices = voices.filter((item) => item.locale === language)

  const handleLanguageChange = async (value: string) => {
    setLanguage(value)
    const first = voices.find((item) => item.locale === value)
    const nextVoice = first ? first.short_name : voice
    setVoice(nextVoice)
    await updateProject(project.id, {
      settings: { ...project.settings, language: value, voice: nextVoice },
    })
    onProjectUpdated?.()
  }

  const handleVoiceChange = async (value: string) => {
    setVoice(value)
    await updateProject(project.id, {
      settings: { ...project.settings, voice: value },
    })
    onProjectUpdated?.()
  }

  const handleProviderChange = async (value: string) => {
    setLlmProvider(value)
    setLlmModel('')
    await updateProject(project.id, {
      settings: { ...project.settings, llm_provider: value, llm_model: '' },
    })
    onProjectUpdated?.()
  }

  const handleModelChange = async (value: string) => {
    setLlmModel(value)
    await updateProject(project.id, {
      settings: { ...project.settings, llm_provider: llmProvider, llm_model: value },
    })
    onProjectUpdated?.()
  }

  const handleStyleChange = async (value: string) => {
    setVideoStyle(value)
    await updateProject(project.id, { video_style: value })
    onProjectUpdated?.()
  }

  const handleGenerate = async () => {
    setError(null)
    try {
      const job = await generateScript(project.id, {
        synopsis,
        video_style: videoStyle,
        num_episodes: numEpisodes,
        episode_duration_seconds: duration,
        language,
      })
      setJobId(job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar el guion')
    }
  }

  const handleConfirm = async () => {
    setError(null)
    setConfirming(true)
    try {
      await confirmScript(project.id)
      await refresh()
      onProjectUpdated?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al confirmar el guion')
    } finally {
      setConfirming(false)
    }
  }

  const episodes = draft?.episodes ?? []
  const isOpen = (episode: ScriptEpisodeDraft) => expanded[episode.number] ?? true
  const setAll = (open: boolean) => {
    setExpanded(Object.fromEntries(episodes.map((episode) => [episode.number, open])))
  }
  const anyCollapsed = episodes.some((episode) => !isOpen(episode))

  return (
    <div className="space-y-6">
      <Card className="relative">
        <CardHeader>
          <p className="slug">Paso 1 · Guion</p>
          <CardTitle className="flex items-center gap-2 text-lg">Generar guion con IA</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="synopsis">Sinopsis</Label>
            <Textarea
              id="synopsis"
              value={synopsis}
              onChange={(event) => setSynopsis(event.target.value)}
              placeholder="Describe tu historia en 2-4 frases: protagonista, conflicto y giro final. Ej: Un hacker descubre que su jefe es una IA y debe elegir entre exponerla o salvar a su hermano…"
              rows={4}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label htmlFor="style">Estilo</Label>
              <StyleSelect id="style" value={videoStyle} onChange={(value) => void handleStyleChange(value)} className="w-full" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="episodes">Episodios</Label>
              <Input
                id="episodes"
                type="number"
                min={1}
                value={numEpisodes}
                onChange={(event) => setNumEpisodes(Number(event.target.value))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="duration">Duración por episodio (s)</Label>
              <Input
                id="duration"
                type="number"
                min={10}
                value={duration}
                onChange={(event) => setDuration(Number(event.target.value))}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="language">Idioma</Label>
              <Select
                value={language}
                onValueChange={(value) => value && void handleLanguageChange(value)}
              >
                <SelectTrigger id="language" aria-label="Idioma" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {locales.length === 0 ? (
                    <SelectItem value={language}>{language}</SelectItem>
                  ) : (
                    locales.map((loc) => (
                      <SelectItem key={loc} value={loc}>
                        {loc}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="voice">Voz</Label>
              <Select
                value={voice || '__default__'}
                onValueChange={(value) =>
                  value && void handleVoiceChange(value === '__default__' ? '' : value)
                }
              >
                <SelectTrigger id="voice" aria-label="Voz" className="w-full">
                  <SelectValue placeholder="Voz por defecto" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">Voz por defecto del idioma</SelectItem>
                  {localeVoices.map((item) => (
                    <SelectItem key={item.short_name} value={item.short_name}>
                      {item.friendly_name || item.short_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void handleGenerate()} disabled={!synopsis.trim()}>
              <Sparkles />
              Generar guion
            </Button>
            <ProviderSelector
              kind="llm"
              value={llmProvider}
              label="Modelo"
              onChange={(value) => void handleProviderChange(value)}
              model={llmModel}
              onModelChange={(value) => void handleModelChange(value)}
            />
          </div>
          {jobId && (
            <JobProgress
              key={jobId}
              jobId={jobId}
              onRetry={() => void handleGenerate()}
              onComplete={() => void refresh()}
            />
          )}
        </CardContent>
      </Card>

      {draft && (
        <section aria-label="Guion generado" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="slug">Guion generado</p>
              <h3 className="mt-1 text-lg font-semibold tracking-tight">Lectura del guion</h3>
            </div>
            {confirmed ? (
              <DoneCheck />
            ) : (
              <Button onClick={() => void handleConfirm()} disabled={confirming}>
                <CheckCircle2 />
                {confirming ? 'Confirmando…' : 'Confirmar guion'}
              </Button>
            )}
          </div>

          {draft.synopsis && (
            <Card>
              <CardHeader>
                <p className="slug">Sinopsis</p>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-foreground/90">{draft.synopsis}</p>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 sm:grid-cols-3">
            <ResourceGroup title="Personajes" items={draft.characters} />
            <ResourceGroup title="Escenas" items={draft.scenes} />
            <ResourceGroup title="Utilería" items={draft.props} />
          </div>

          {episodes.length > 0 && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h4 className="text-sm font-semibold tracking-tight">
                  Capítulos
                  <span className="timecode ml-2 align-middle text-sm font-normal text-muted-foreground">
                    {episodes.length}
                  </span>
                </h4>
                {episodes.length > 1 && (
                  <Button variant="outline" size="sm" onClick={() => setAll(anyCollapsed)}>
                    <ListTree />
                    {anyCollapsed ? 'Desplegar todo' : 'Colapsar todo'}
                  </Button>
                )}
              </div>
              <div className="space-y-4">
                {episodes.map((episode, index) => (
                  <DraftChapter
                    key={episode.number}
                    episode={episode}
                    open={isOpen(episode)}
                    onToggle={() =>
                      setExpanded((prev) => ({
                        ...prev,
                        [episode.number]: !(prev[episode.number] ?? true),
                      }))
                    }
                    index={index}
                  />
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function ResourceGroup({ title, items }: { title: string; items: ScriptResource[] }) {
  return (
    <Card>
      <CardHeader>
        <p className="slug">{title}</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">—</p>
        ) : (
          items.map((item) => (
            <div key={item.name}>
              <p className="text-sm font-medium">{item.name}</p>
              {item.description && (
                <p className="text-xs text-muted-foreground">{item.description}</p>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

function DraftChapter({
  episode,
  open,
  onToggle,
  index,
}: {
  episode: ScriptEpisodeDraft
  open: boolean
  onToggle: () => void
  index: number
}) {
  const shots = episode.shots.length
  const seconds = shots * 10
  const contentId = `draft-chapter-${episode.number}-body`

  return (
    <Card
      className="group animate-frame-in overflow-hidden"
      style={{ animationDelay: `${Math.min(index, 8) * 50}ms` }}
    >
      <div className="flex items-center gap-3 px-(--card-spacing)">
        <span className="timecode flex size-11 shrink-0 items-center justify-center rounded-lg border border-border bg-muted/40 text-base font-semibold text-foreground/85">
          {String(episode.number).padStart(2, '0')}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm leading-tight font-medium">
            {episode.title || `Capítulo ${episode.number}`}
          </p>
          <p className="slug mt-1 truncate">
            Capítulo {episode.number} · <span className="text-pencil">{formatDuration(seconds)}</span> ·{' '}
            {shots} {shots === 1 ? 'plano' : 'planos'}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={onToggle}
          className="text-muted-foreground"
        >
          <ChevronDown className={cn('transition-transform duration-300', open && 'rotate-180')} />
          <span className="sr-only">{open ? 'Colapsar capítulo' : 'Desplegar capítulo'}</span>
        </Button>
      </div>

      <div
        id={contentId}
        className={cn(
          'grid transition-[grid-template-rows] duration-300 ease-out',
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="overflow-hidden">
          <div className="space-y-3 px-(--card-spacing) pt-3">
            {episode.shots.map((shot) => (
              <div
                key={shot.shot_number}
                className="rounded-xl border border-border bg-muted/20 p-3 transition-colors hover:border-border/80"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="timecode text-xs font-semibold text-pencil">
                    [{episode.number}-{shot.shot_number}]
                  </span>
                  <span className="slug">{shot.time_place}</span>
                  <span className="timecode ml-auto text-xs text-muted-foreground">
                    {formatDuration(10)}
                  </span>
                </div>
                {shot.cast.length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">Reparto: {shot.cast.join(', ')}</p>
                )}
                <p className="mt-2 text-sm text-muted-foreground">{shot.action}</p>
                {shot.dialogues.map((line, i) => (
                  <p key={i} className="mt-1 text-sm italic text-foreground/90">
                    — {line.character}: {line.text}
                  </p>
                ))}
              </div>
            ))}
            {shots === 0 && (
              <p className="text-sm text-muted-foreground">Este capítulo aún no tiene planos.</p>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}
