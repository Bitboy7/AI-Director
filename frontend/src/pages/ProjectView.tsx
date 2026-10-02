import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getProject } from '@/lib/api'
import ResourcesStep from '@/pages/steps/ResourcesStep'
import ScriptStep from '@/pages/steps/ScriptStep'
import VideosStep from '@/pages/steps/VideosStep'
import type { Project } from '@/types'

export default function ProjectView() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)

  useEffect(() => {
    void getProject(Number(projectId)).then(setProject).catch(() => setProject(null))
  }, [projectId])

  if (!project) return <main className="p-6 text-muted-foreground">Cargando…</main>

  return (
    <main className="mx-auto max-w-6xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{project.name}</h2>
          <p className="text-sm text-muted-foreground">{project.synopsis}</p>
        </div>
        <Button variant="outline" onClick={() => navigate('/')}>
          ← Proyectos
        </Button>
      </div>
      <Tabs defaultValue="script">
        <TabsList className="mb-4">
          <TabsTrigger value="script">1 · Esquema del guion</TabsTrigger>
          <TabsTrigger value="resources">2 · Biblioteca de recursos</TabsTrigger>
          <TabsTrigger value="videos">3 · Videos por episodio</TabsTrigger>
        </TabsList>
        <TabsContent value="script">
          <ScriptStep project={project} />
        </TabsContent>
        <TabsContent value="resources">
          <ResourcesStep projectId={project.id} />
        </TabsContent>
        <TabsContent value="videos">
          <VideosStep project={project} />
        </TabsContent>
      </Tabs>
    </main>
  )
}
