import { useEffect, useState } from 'react'
import { ArrowLeft, BarChart3, Lock } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Button, buttonVariants } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DoneCheck } from '@/components/stamp'
import { cn } from '@/lib/utils'
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
  const [activeTab, setActiveTab] = useState<string | null>(null)

  const refresh = async () => {
    setProject(await getProject(Number(projectId)))
  }

  useEffect(() => {
    void refresh().catch(() => setProject(null))
  }, [projectId])

  if (!project) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-8 text-muted-foreground sm:px-6">
        Cargando…
      </main>
    )
  }

  const completedPhases = (project.settings.completed_phases ?? []) as number[]
  const canOpen = (phase: number) => phase === 1 || completedPhases.includes(phase - 1)
  const currentTab = completedPhases.includes(2)
    ? 'videos'
    : completedPhases.includes(1)
      ? 'resources'
      : 'script'
  const selectedTab = activeTab ?? currentTab
  const currentPhase = selectedTab === 'script' ? 1 : selectedTab === 'resources' ? 2 : 3
  const phaseCompleted = completedPhases.includes(currentPhase)

  const togglePhase = async () => {
    await setPhaseCompleted(project.id, currentPhase, !phaseCompleted)
    setActiveTab(null)
    await refresh()
  }

  const tabs = [
    { value: 'script', number: 1, label: PHASE_LABELS[1] },
    { value: 'resources', number: 2, label: PHASE_LABELS[2], locked: !canOpen(2) },
    { value: 'videos', number: 3, label: PHASE_LABELS[3], locked: !canOpen(3) },
  ]

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/')}
            aria-label="Volver a proyectos"
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
            <p className="mt-0.5 max-w-prose text-sm text-muted-foreground">
              {project.synopsis}
            </p>
          </div>
        </div>
        {canOpen(currentPhase) && (
          <div className="flex items-center gap-2">
            <Link
              to={`/stats?project=${project.id}`}
              className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }))}
            >
              <BarChart3 className="size-4" />
              Estadísticas
            </Link>
            <Button
              size="sm"
              variant={phaseCompleted ? 'outline' : 'default'}
              onClick={() => void togglePhase()}
            >
              {phaseCompleted ? 'Reabrir fase' : `Marcar fase ${currentPhase} como completada`}
            </Button>
          </div>
        )}
      </div>

      <Tabs value={selectedTab} onValueChange={setActiveTab}>
        <TabsList
          variant="line"
          className="mb-6 grid! w-full! h-auto! grid-cols-1 gap-2! rounded-none! bg-transparent p-0! sm:grid-cols-3"
        >
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              disabled={tab.locked}
              className={cn('group w-full after:hidden!', tab.locked && 'opacity-55')}
            >
              <span
                className={cn(
                  'relative flex min-h-[4.25rem] w-full flex-col items-start justify-between gap-1.5 overflow-hidden rounded-xl border border-border bg-card px-3 py-2.5 text-left transition-all duration-300',
                  'group-data-[active]:border-pencil/70 group-data-[active]:bg-pencil/10 group-data-[active]:shadow-[0_0_0_1px_color-mix(in_oklch,var(--pencil)_70%,transparent),0_14px_32px_-18px_color-mix(in_oklch,var(--pencil)_45%,transparent)]',
                )}
              >
                <span className="flex w-full items-center justify-between">
                  <span className="timecode text-lg leading-none font-semibold text-foreground/85">
                    {String(tab.number).padStart(2, '0')}
                  </span>
                  {completedPhases.includes(tab.number) ? (
                    <DoneCheck />
                  ) : tab.locked ? (
                    <Lock className="size-3.5 text-muted-foreground" />
                  ) : null}
                </span>
                <span className="text-sm leading-tight font-medium">{tab.label}</span>
              </span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="script" className="animate-tab-in">
          <ScriptStep project={project} onProjectUpdated={() => void refresh()} />
        </TabsContent>
        <TabsContent value="resources" className="animate-tab-in">
          <ResourcesStep project={project} onProjectUpdated={() => void refresh()} />
        </TabsContent>
        <TabsContent value="videos" className="animate-tab-in">
          <VideosStep project={project} onProjectUpdated={() => void refresh()} />
        </TabsContent>
      </Tabs>
    </main>
  )
}