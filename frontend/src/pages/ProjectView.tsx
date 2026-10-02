import { useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getProject, setPhaseCompleted } from '@/lib/api'
import ResourcesStep from '@/pages/steps/ResourcesStep'
import ScriptStep from '@/pages/steps/ScriptStep'
import VideosStep from '@/pages/steps/VideosStep'
import type { Project } from '@/types'

const PHASE_LABELS: Record<number, string> = {
  1: 'Esquema del guion',
  2: 'Biblioteca de recursos',
  3: 'Videos por episodio',
}

export default function ProjectView() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)

  const refresh = async () => {
    setProject(await getProject(Number(projectId)))
  }

  useEffect(() => {
    void refresh().catch(() => setProject(null))
  }, [projectId])

  if (!project) return <main className="p-6 text-muted-foreground">Cargando…</main>

  const completedPhases = (project.settings.completed_phases ?? []) as number[]
  const canOpen = (phase: number) => phase === 1 || completedPhases.includes(phase - 1)
  const currentTab = completedPhases.includes(2)
    ? 'videos'
    : completedPhases.includes(1)
      ? 'resources'
      : 'script'
  const currentPhase = currentTab === 'script' ? 1 : currentTab === 'resources' ? 2 : 3
  const phaseCompleted = completedPhases.includes(currentPhase)

  const togglePhase = async () => {
    await setPhaseCompleted(project.id, currentPhase, !phaseCompleted)
    await refresh()
  }

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

      <div className="mb-4 flex items-center gap-3 rounded-md border bg-muted/40 p-3">
        <span className="text-sm text-muted-foreground">
          Fase {currentPhase}: {PHASE_LABELS[currentPhase]}
        </span>
        {canOpen(currentPhase) && (
          <Button size="sm" variant={phaseCompleted ? 'outline' : 'default'} onClick={() => void togglePhase()}>
            {phaseCompleted
              ? 'Reabrir fase'
              : `Marcar fase ${currentPhase} como completada`}
          </Button>
        )}
      </div>

      <Tabs value={currentTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="script">1 · Esquema del guion</TabsTrigger>
          <TabsTrigger value="resources" disabled={!canOpen(2)}>
            2 · Biblioteca de recursos
            {!canOpen(2) && <Lock className="ml-1 size-3" />}
          </TabsTrigger>
          <TabsTrigger value="videos" disabled={!canOpen(3)}>
            3 · Videos por episodio
            {!canOpen(3) && <Lock className="ml-1 size-3" />}
          </TabsTrigger>
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
