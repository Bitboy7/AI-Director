import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { createProject, deleteProject, listProjects } from '@/lib/api'
import type { Project } from '@/types'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [synopsis, setSynopsis] = useState('')
  const [videoStyle, setVideoStyle] = useState('')
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
      setVideoStyle('')
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
    <main className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Proyectos</h2>
          <p className="text-sm text-muted-foreground">Historias cortas generadas con IA</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <Button onClick={() => setOpen(true)}>Nuevo proyecto</Button>
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
                <Input
                  id="style"
                  value={videoStyle}
                  onChange={(event) => setVideoStyle(event.target.value)}
                  placeholder="cyberpunk, realista…"
                />
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
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            Aún no hay proyectos. Crea el primero para empezar.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {projects.map((project) => (
            <Card key={project.id} className="group relative">
              <Link to={`/projects/${project.id}`}>
                <CardHeader>
                  <CardTitle className="group-hover:underline">{project.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="line-clamp-2 text-sm text-muted-foreground">
                    {project.synopsis || 'Sin sinopsis'}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {project.video_style || 'estilo libre'} · {project.aspect_ratio} ·{' '}
                    {project.status}
                  </p>
                </CardContent>
              </Link>
              <div className="absolute right-3 top-3 opacity-0 transition-opacity group-hover:opacity-100">
                <Button
                  variant="ghost"
                  size="sm"
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
