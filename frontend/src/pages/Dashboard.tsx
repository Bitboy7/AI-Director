import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Film, Plus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import StyleSelect from '@/components/StyleSelect'
import { createProject, deleteProject, listProjects, projectCoverUrl, DEFAULT_STYLE_ID } from '@/lib/api'
import type { Project } from '@/types'

function ProjectCover({ projectId }: { projectId: number }) {
  const [ok, setOk] = useState(true)
  if (!ok) {
    return <Film className="size-8 text-muted-foreground/40" />
  }
  return (
    <img
      src={projectCoverUrl(projectId)}
      alt=""
      className="h-full w-full object-cover"
      onError={() => setOk(false)}
    />
  )
}

const STATUS_LABEL: Record<string, string> = {
  draft: 'borrador',
  active: 'en rodaje',
  done: 'terminada',
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [synopsis, setSynopsis] = useState('')
  const [videoStyle, setVideoStyle] = useState(DEFAULT_STYLE_ID)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setProjects(await listProjects())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error cargando proyectos')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleCreate = async () => {
    setError(null)
    try {
      await createProject(name.trim(), synopsis, videoStyle, '16:9')
      setOpen(false)
      setName('')
      setSynopsis('')
      setVideoStyle(DEFAULT_STYLE_ID)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error creando proyecto')
    }
  }

  const handleDelete = async (id: number) => {
    setError(null)
    try {
      await deleteProject(id)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error borrando proyecto')
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="slug mb-2">Salas de rodaje</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Proyectos
            {projects.length > 0 && (
              <span className="timecode ml-3 align-middle text-sm font-normal text-muted-foreground">
                {projects.length}
              </span>
            )}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Historias cortas generadas con IA, capítulo a capítulo.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <Button onClick={() => setOpen(true)}>
            <Plus />
            Nuevo proyecto
          </Button>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Crear proyecto</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="name">Nombre</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Neon Rebellion"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="synopsis">Sinopsis</Label>
                <Textarea
                  id="synopsis"
                  value={synopsis}
                  onChange={(event) => setSynopsis(event.target.value)}
                  placeholder="Un hacker descubre un secreto…"
                  rows={3}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="style">Estilo de video</Label>
                <StyleSelect id="style" value={videoStyle} onChange={setVideoStyle} className="w-full" />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button onClick={() => void handleCreate()} disabled={!name.trim()}>
                Crear
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {projects.length === 0 ? (
        <Card className="border border-dashed border-border/60 bg-transparent ring-0">
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <span className="flex size-12 items-center justify-center rounded-xl border border-border bg-muted/40">
              <Film className="size-5 text-muted-foreground" />
            </span>
            <div>
              <p className="font-medium">Aún no hay proyectos</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Crea el primero para empezar tu serie.
              </p>
            </div>
            <Button variant="outline" onClick={() => setOpen(true)}>
              <Plus />
              Crear el primero
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project, index) => (
            <Card
              key={project.id}
              className="group animate-frame-in transition-all duration-300 hover:-translate-y-0.5 hover:ring-pencil/60 hover:shadow-[0_18px_44px_-20px_color-mix(in_oklch,var(--pencil)_40%,transparent)]"
              style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
            >
              <Link to={`/projects/${project.id}`} className="flex h-full flex-col">
                <div className="relative flex aspect-video items-center justify-center overflow-hidden border-b border-border bg-gradient-to-br from-muted/70 via-muted/40 to-muted/10">
                  <ProjectCover projectId={project.id} />
                  <span className="slug absolute top-3 left-3">
                    FR.{String(project.id).padStart(2, '0')}
                  </span>
                  <span className="timecode absolute right-3 bottom-3 rounded-sm border border-border bg-background/60 px-1.5 py-0.5 text-[0.6875rem] text-muted-foreground">
                    {project.aspect_ratio}
                  </span>
                </div>
                <CardHeader>
                  <CardTitle className="flex items-start justify-between gap-2">
                    <span className="group-hover:underline">{project.name}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-3">
                  <p className="line-clamp-2 flex-1 text-sm text-muted-foreground">
                    {project.synopsis || 'Sin sinopsis'}
                  </p>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{project.video_style || 'estilo libre'}</Badge>
                    <Badge variant="outline">
                      {STATUS_LABEL[project.status] ?? project.status}
                    </Badge>
                  </div>
                </CardContent>
              </Link>
              <div className="absolute top-3 right-3 z-20 opacity-0 transition-opacity group-hover:opacity-100">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  onClick={() => void handleDelete(project.id)}
                >
                  Borrar
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </main>
  )
}