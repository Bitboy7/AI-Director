import { useEffect, useState } from 'react'
import { ArrowLeft, ImageIcon, Plus, Sparkles } from 'lucide-react'
import AssetPicker from '@/components/AssetPicker'
import JobProgress from '@/components/JobProgress'
import ProviderSelector from '@/components/ProviderSelector'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  assetUrl,
  createResource,
  createVariant,
  generateReferenceImage,
  generateResourceImages,
  generateResources,
  getVoices,
  listResources,
  updateProject,
  updateResource,
  updateVariant,
  type VoiceOption,
} from '@/lib/api'
import type { Project, ReferenceImage, Resource, ResourceType } from '@/types'

interface Props {
  project: Project
  onProjectUpdated: () => void
}

const TYPE_LABEL: Record<ResourceType, string> = {
  character: 'Personajes',
  scene: 'Escenas',
  prop: 'Utilería',
}

const TYPE_SINGULAR: Record<ResourceType, string> = {
  character: 'Personaje',
  scene: 'Escena',
  prop: 'Utilería',
}

function coverOf(resource: Resource): ReferenceImage | undefined {
  return (
    resource.variants
      .flatMap((variant) => variant.reference_images)
      .find((image) => image.origin === 'generated') ??
    resource.variants[0]?.reference_images[0]
  )
}

export default function ResourcesStep({ project, onProjectUpdated }: Props) {
  const projectId = project.id
  const [resources, setResources] = useState<Resource[]>([])
  const [jobId, setJobId] = useState<number | null>(null)
  const [imageJobId, setImageJobId] = useState<number | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [preview, setPreview] = useState<string | null>(null)
  const [detail, setDetail] = useState<Resource | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [imageProvider, setImageProvider] = useState(
    (project.settings.image_provider as string | undefined) ?? 'gemini',
  )
  const [imageModel, setImageModel] = useState(
    (project.settings.image_model as string | undefined) ?? '',
  )

  const refresh = async () => setResources(await listResources(projectId))

  useEffect(() => {
    void refresh()
  }, [projectId])

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allSelected = resources.length > 0 && selected.size === resources.length
  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(resources.map((resource) => resource.id)))
  }

  const handleProviderChange = async (value: string) => {
    setImageProvider(value)
    setImageModel('')
    await updateProject(projectId, {
      settings: { ...project.settings, image_provider: value, image_model: '' },
    })
    onProjectUpdated()
  }

  const handleModelChange = async (value: string) => {
    setImageModel(value)
    await updateProject(projectId, {
      settings: { ...project.settings, image_provider: imageProvider, image_model: value },
    })
    onProjectUpdated()
  }

  const handleGenerate = async () => {
    setError(null)
    try {
      const job = await generateResources(projectId)
      setJobId(job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar variantes')
    }
  }

  const handleGenerateImages = async () => {
    if (selected.size === 0) return
    setError(null)
    try {
      const job = await generateResourceImages(projectId, {
        resource_ids: [...selected],
        provider: imageProvider,
        model: imageModel || undefined,
      })
      setImageJobId(job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar las imágenes')
    }
  }

  const createNew = async (type: ResourceType, name: string) => {
    await createResource(projectId, type, name)
    await refresh()
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-md text-sm text-muted-foreground">
          La biblioteca se usa en todo el proyecto. Haz clic en una card para ver y
          editar toda su información.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <ProviderSelector
            kind="image"
            value={imageProvider}
            label="Imágenes"
            onChange={(value) => void handleProviderChange(value)}
            model={imageModel}
            onModelChange={(value) => void handleModelChange(value)}
          />
          <Button onClick={() => void handleGenerateImages()} disabled={selected.size === 0}>
            <Sparkles />
            Generar imágenes{selected.size > 0 ? ` (${selected.size})` : ''}
          </Button>
          <Button onClick={() => void handleGenerate()} variant="outline">
            <Sparkles />
            Generar variantes con IA
          </Button>
        </div>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {jobId && <JobProgress key={jobId} jobId={jobId} onRetry={() => void handleGenerate()} />}
      {imageJobId && (
        <JobProgress
          key={`images-${imageJobId}`}
          jobId={imageJobId}
          onComplete={() => {
            setSelected(new Set())
            void refresh()
          }}
        />
      )}

      <Tabs defaultValue="character">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            {(['character', 'scene', 'prop'] as ResourceType[]).map((type) => (
              <TabsTrigger key={type} value={type}>
                {TYPE_LABEL[type]}
                <span className="timecode ml-1 text-xs text-muted-foreground">
                  {resources.filter((resource) => resource.type === type).length}
                </span>
              </TabsTrigger>
            ))}
          </TabsList>
          {resources.length > 0 && (
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                className="size-4 accent-[var(--pencil)]"
              />
              Seleccionar todo
            </label>
          )}
        </div>
        {(['character', 'scene', 'prop'] as ResourceType[]).map((type) => (
          <TabsContent key={type} value={type} className="animate-tab-in">
            <ResourceGrid
              resources={resources.filter((resource) => resource.type === type)}
              type={type}
              selected={selected}
              onToggleSelect={toggleSelect}
              onOpen={setDetail}
              onPreview={setPreview}
              onCreate={(name) => void createNew(type, name)}
            />
          </TabsContent>
        ))}
      </Tabs>

      <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-h-[92vh] w-[96vw] overflow-y-auto sm:w-[92vw] sm:max-w-6xl">
          <DialogTitle className="sr-only">Información del recurso</DialogTitle>
          {detail && (
            <ResourceDetail
              resource={detail}
              onClose={() => setDetail(null)}
              onChanged={() => void refresh()}
              onPreview={setPreview}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={preview !== null} onOpenChange={(open) => !open && setPreview(null)}>
        <DialogContent className="max-h-[92vh] w-[96vw] overflow-y-auto sm:w-[92vw] sm:max-w-4xl">
          <DialogTitle className="sr-only">Vista ampliada</DialogTitle>
          {preview && (
            <img
              src={assetUrl(preview)}
              alt="Vista ampliada"
              className="w-full rounded-lg bg-white"
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

interface GridProps {
  resources: Resource[]
  type: ResourceType
  selected: Set<number>
  onToggleSelect: (id: number) => void
  onOpen: (resource: Resource) => void
  onPreview: (path: string) => void
  onCreate: (name: string) => void
}

function ResourceGrid({
  resources,
  type,
  selected,
  onToggleSelect,
  onOpen,
  onCreate,
}: GridProps) {
  const [newName, setNewName] = useState('')

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder={`Nuevo ${TYPE_SINGULAR[type].toLowerCase()}`}
          className="max-w-xs"
          onKeyDown={(event) => {
            if (event.key === 'Enter' && newName.trim()) {
              onCreate(newName.trim())
              setNewName('')
            }
          }}
        />
        <Button
          variant="outline"
          onClick={() => {
            if (!newName.trim()) return
            onCreate(newName.trim())
            setNewName('')
          }}
        >
          <Plus />
          Añadir
        </Button>
      </div>

      {resources.length === 0 ? (
        <Card className="border-dashed bg-transparent">
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <ImageIcon className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Aún no hay {TYPE_LABEL[type].toLowerCase()}. Crea el primero o genera
              variantes con IA.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {resources.map((resource) => {
            const cover = coverOf(resource)
            return (
              <div key={resource.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onOpen(resource)}
                  aria-label={resource.name}
                  className="w-full overflow-hidden rounded-xl border border-border bg-card text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-pencil/50 hover:shadow-[0_18px_44px_-24px_color-mix(in_oklch,var(--pencil)_50%,transparent)]"
                >
                  <div className="relative aspect-square w-full overflow-hidden bg-white">
                    {cover ? (
                      <img
                        src={assetUrl(cover.path)}
                        alt={resource.name}
                        className="h-full w-full object-contain p-2 transition-transform duration-500 group-hover:scale-[1.03]"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center">
                        <ImageIcon className="size-8 text-neutral-300" />
                      </div>
                    )}
                    <span className="slug absolute top-2 left-2 rounded-sm bg-neutral-900/80 px-1.5 py-0.5 text-white">
                      {TYPE_SINGULAR[type]}
                    </span>
                    {resource.variants.length > 0 && (
                      <Badge variant="secondary" className="absolute top-2 right-2">
                        {resource.variants.length}{' '}
                        {resource.variants.length === 1 ? 'variante' : 'variantes'}
                      </Badge>
                    )}
                  </div>
                  <div className="px-3 py-2.5">
                    <p className="truncate text-sm font-medium">{resource.name}</p>
                  </div>
                </button>
                <label className="absolute top-2 right-2 z-10 flex size-6 cursor-pointer items-center justify-center rounded-md border border-border bg-background/80 backdrop-blur-sm">
                  <input
                    type="checkbox"
                    checked={selected.has(resource.id)}
                    onChange={() => onToggleSelect(resource.id)}
                    aria-label={`Seleccionar ${resource.name}`}
                    className="size-3.5 accent-[var(--pencil)]"
                  />
                </label>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

interface DetailProps {
  resource: Resource
  onClose: () => void
  onChanged: () => void
  onPreview: (path: string) => void
}

function ResourceDetail({ resource, onClose, onChanged, onPreview }: DetailProps) {
  const [name, setName] = useState(resource.name)
  const [variantId, setVariantId] = useState<number | null>(
    resource.variants[0]?.id ?? null,
  )
  const variant = resource.variants.find((item) => item.id === variantId) ?? null
  const [variantName, setVariantName] = useState(variant?.name ?? '')
  const [prompt, setPrompt] = useState(variant?.description ?? '')
  const [voice, setVoice] = useState((variant?.voice?.voice as string) ?? '')
  const [voiceNote, setVoiceNote] = useState((variant?.voice?.description as string) ?? '')
  const [voices, setVoices] = useState<VoiceOption[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [newVariant, setNewVariant] = useState('')

  useEffect(() => {
    void getVoices()
      .then(setVoices)
      .catch(() => setVoices([]))
  }, [])

  useEffect(() => {
    setVariantName(variant?.name ?? '')
    setPrompt(variant?.description ?? '')
    setVoice((variant?.voice?.voice as string) ?? '')
    setVoiceNote((variant?.voice?.description as string) ?? '')
  }, [variant])

  const image = variant?.reference_images[variant.reference_images.length - 1]

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      if (name.trim() && name.trim() !== resource.name) {
        await updateResource(resource.id, { name: name.trim() })
      }
      if (variant) {
        await updateVariant(variant.id, {
          name: variantName.trim() || variant.name,
          description: prompt,
          voice: { voice, description: voiceNote },
        })
      }
      onChanged()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al guardar')
    } finally {
      setBusy(false)
    }
  }

  const generate = async () => {
    if (!variant) return
    setBusy(true)
    setError(null)
    try {
      await generateReferenceImage(variant.id, { prompt: prompt.trim() || undefined })
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar la imagen')
    } finally {
      setBusy(false)
    }
  }

  const addVariant = async () => {
    if (!newVariant.trim()) return
    const created = await createVariant(resource.id, { name: newVariant.trim() })
    setNewVariant('')
    onChanged()
    setVariantId(created.id)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Volver">
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <p className="slug">{TYPE_SINGULAR[resource.type]}</p>
          <h2 className="text-lg font-semibold tracking-tight">Información del recurso</h2>
        </div>
      </div>

      {resource.variants.length > 0 && (
        <Tabs
          value={variantId ? String(variantId) : undefined}
          onValueChange={(value) => value && setVariantId(Number(value))}
        >
          <TabsList>
            {resource.variants.map((item) => (
              <TabsTrigger key={item.id} value={String(item.id)}>
                {item.name}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="detail-name">Nombre</Label>
            <Input id="detail-name" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          {variant && (
            <>
              <div className="space-y-1">
                <Label htmlFor="detail-variant">Nombre de la variante</Label>
                <Input
                  id="detail-variant"
                  value={variantName}
                  onChange={(event) => setVariantName(event.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="detail-voice">Voz</Label>
                <Select
                  value={voice || '__default__'}
                  onValueChange={(value) =>
                    value && setVoice(value === '__default__' ? '' : value)
                  }
                >
                  <SelectTrigger id="detail-voice" aria-label="Voz" className="w-full">
                    <SelectValue placeholder="IA automática" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__default__">IA automática</SelectItem>
                    {voices.map((item) => (
                      <SelectItem key={item.short_name} value={item.short_name}>
                        {item.friendly_name || item.short_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="detail-voice-note">Descripción del timbre</Label>
                <Textarea
                  id="detail-voice-note"
                  value={voiceNote}
                  maxLength={100}
                  onChange={(event) => setVoiceNote(event.target.value)}
                  placeholder="Introduce el contenido"
                  rows={2}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="detail-prompt">Descripción / prompt</Label>
                <Textarea
                  id="detail-prompt"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  rows={6}
                />
              </div>
              <div className="flex gap-2">
                <Input
                  value={newVariant}
                  onChange={(event) => setNewVariant(event.target.value)}
                  placeholder="Nueva variante"
                />
                <Button variant="outline" onClick={() => void addVariant()}>
                  <Plus />
                </Button>
              </div>
            </>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button onClick={() => void save()} disabled={busy} className="w-full">
            Guardar
          </Button>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium">
            {name} {variant ? `- ${variantName}` : ''}
          </p>
          <div className="rounded-xl border border-border bg-white p-4">
            <div className="flex aspect-[4/3] items-center justify-center">
              {image ? (
                <button
                  type="button"
                  onClick={() => onPreview(image.path)}
                  className="h-full w-full cursor-zoom-in"
                  aria-label="Ampliar imagen"
                >
                  <img
                    src={assetUrl(image.path)}
                    alt={resource.name}
                    className="h-full w-full object-contain"
                  />
                </button>
              ) : (
                <ImageIcon className="size-10 text-neutral-300" />
              )}
            </div>
          </div>
          {variant && (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => void generate()} disabled={busy}>
                <Sparkles />
                {busy ? 'Generando…' : 'Generar'}
              </Button>
              <AssetPicker variantId={variant.id} onUploaded={() => onChanged()} />
            </div>
          )}
          {variant && variant.reference_images.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {variant.reference_images.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onPreview(item.path)}
                  className="size-16 overflow-hidden rounded-lg border border-border bg-white"
                >
                  <img src={assetUrl(item.path)} alt="" className="h-full w-full object-contain" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
