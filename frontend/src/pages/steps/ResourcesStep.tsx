import { useEffect, useState } from 'react'
import AssetPicker from '@/components/AssetPicker'
import JobProgress from '@/components/JobProgress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { createResource, createVariant, generateResources, listResources } from '@/lib/api'
import type { ReferenceImage, Resource, ResourceType } from '@/types'

interface Props {
  projectId: number
}

const TYPE_LABEL: Record<ResourceType, string> = {
  character: 'Personajes',
  scene: 'Escenas',
  prop: 'Utilería',
}

export default function ResourcesStep({ projectId }: Props) {
  const [resources, setResources] = useState<Resource[]>([])
  const [jobId, setJobId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => setResources(await listResources(projectId))

  useEffect(() => {
    void refresh()
  }, [projectId])

  const handleGenerate = async () => {
    setError(null)
    try {
      const job = await generateResources(projectId)
      setJobId(job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar variantes')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Los recursos se usan en todo el proyecto. Genera variantes o créalas a mano.
        </p>
        <Button onClick={() => void handleGenerate()} variant="outline">
          Generar variantes con IA
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {jobId && (
        <JobProgress key={jobId} jobId={jobId} onRetry={() => void handleGenerate()} />
      )}

      <Tabs defaultValue="character">
        <TabsList>
          {(['character', 'scene', 'prop'] as ResourceType[]).map((type) => (
            <TabsTrigger key={type} value={type}>
              {TYPE_LABEL[type]}
            </TabsTrigger>
          ))}
        </TabsList>
        {(['character', 'scene', 'prop'] as ResourceType[]).map((type) => (
          <TabsContent key={type} value={type}>
            <ResourceList
              resources={resources.filter((resource) => resource.type === type)}
              projectId={projectId}
              type={type}
              onChanged={() => void refresh()}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}

interface ListProps {
  resources: Resource[]
  projectId: number
  type: ResourceType
  onChanged: () => void
}

function ResourceList({ resources, projectId, type, onChanged }: ListProps) {
  const [newName, setNewName] = useState('')

  const handleCreate = async () => {
    if (!newName.trim()) return
    await createResource(projectId, type, newName.trim())
    setNewName('')
    onChanged()
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder={`Nuevo ${TYPE_LABEL[type].toLowerCase().slice(0, -1)}`}
          className="max-w-xs"
        />
        <Button variant="outline" onClick={() => void handleCreate()}>
          Añadir
        </Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {resources.map((resource) => (
          <Card key={resource.id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                {resource.name}
                <Badge variant="secondary">{resource.variants.length} variantes</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {resource.variants.map((variant) => (
                <VariantCard key={variant.id} resourceId={resource.id} variant={variant} onChanged={onChanged} />
              ))}
              <NewVariant resourceId={resource.id} onCreated={onChanged} />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

interface VariantProps {
  resourceId: number
  variant: Resource['variants'][number]
  onChanged: () => void
}

function VariantCard({ variant, onChanged }: VariantProps) {
  const [images, setImages] = useState<ReferenceImage[]>(variant.reference_images)

  return (
    <div className="rounded-md border p-3">
      <p className="text-sm font-medium">{variant.name}</p>
      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{variant.description}</p>
      {variant.episodes.length > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          Episodios: {variant.episodes.join(', ')}
        </p>
      )}
      <div className="mt-2">
        <AssetPicker
          variantId={variant.id}
          images={images}
          onUploaded={(image) => {
            setImages((prev) => [...prev, image])
            onChanged()
          }}
        />
      </div>
    </div>
  )
}

function NewVariant({ resourceId, onCreated }: { resourceId: number; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const handleCreate = async () => {
    if (!name.trim()) return
    await createVariant(resourceId, { name: name.trim(), description })
    setName('')
    setDescription('')
    onCreated()
  }

  return (
    <div className="space-y-2 rounded-md border border-dashed p-3">
      <Label htmlFor={`variant-name-${resourceId}`}>Nueva variante</Label>
      <Input
        id={`variant-name-${resourceId}`}
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Base Appearance"
      />
      <Textarea
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        placeholder="Prompt visual de la variante"
        rows={2}
      />
      <Button size="sm" variant="outline" onClick={() => void handleCreate()}>
        Crear variante
      </Button>
    </div>
  )
}
