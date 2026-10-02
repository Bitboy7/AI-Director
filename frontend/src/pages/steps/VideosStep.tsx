import { useEffect, useState } from 'react'
import JobProgress from '@/components/JobProgress'
import VideoPlayer from '@/components/VideoPlayer'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { assetUrl, generateEpisode, generateFragment, listEpisodes } from '@/lib/api'
import type { Episode, Project } from '@/types'

interface Props {
  project: Project
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente',
  generated: 'Generado',
}

export default function VideosStep({ project }: Props) {
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [assemblyJobId, setAssemblyJobId] = useState<number | null>(null)
  const [fragmentJobIds, setFragmentJobIds] = useState<Record<number, number>>({})
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => setEpisodes(await listEpisodes(project.id))

  useEffect(() => {
    void refresh()
  }, [project.id])

  useEffect(() => {
    if (!selectedId && episodes.length > 0) setSelectedId(String(episodes[0].id))
  }, [episodes, selectedId])

  const episode = episodes.find((ep) => String(ep.id) === selectedId) ?? null
  const hasAssembly = episode != null && assemblyJobId != null
  const finalPath = `${project.id}/episodes/${episode?.id}/final.mp4`

  const handleGenerateEpisode = async () => {
    if (!episode) return
    setError(null)
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

  const handleGenerateFragment = async (fragmentId: number) => {
    setError(null)
    try {
      const job = await generateFragment(fragmentId)
      setFragmentJobIds((prev) => ({ ...prev, [fragmentId]: job.id }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar el fragmento')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <Select
          value={selectedId}
          onValueChange={(value) => {
            if (value) setSelectedId(value)
          }}
        >
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Selecciona un episodio" />
          </SelectTrigger>
          <SelectContent>
            {episodes.map((ep) => (
              <SelectItem key={ep.id} value={String(ep.id)}>
                Episodio {ep.number}: {ep.title || `sin título`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {episode && (
          <Button onClick={() => void handleGenerateEpisode()}>
            Generar episodio completo
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {hasAssembly && (
        <JobProgress
          key={`assembly-${assemblyJobId}`}
          jobId={assemblyJobId as number}
          onRetry={() => void handleGenerateEpisode()}
        />
      )}

      {episode && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Video final</CardTitle>
            </CardHeader>
            <CardContent>
              <VideoPlayer
                path={
                  episode.fragments.every((fragment) => fragment.status === 'generated')
                    ? finalPath
                    : null
                }
              />
            </CardContent>
          </Card>
          <div className="space-y-3">
            {episode.fragments.map((fragment) => (
              <Card key={fragment.id}>
                <CardContent className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">
                      [{episode.number}-{fragment.shot_number}] {fragment.time_place}
                    </p>
                    <p className="line-clamp-1 text-xs text-muted-foreground">
                      {fragment.prompt_video}
                    </p>
                    <Badge variant={fragment.status === 'generated' ? 'outline' : 'secondary'} className="mt-1">
                      {STATUS_LABEL[fragment.status] ?? fragment.status}
                    </Badge>
                  </div>
                  {fragment.video_path ? (
                    <video
                      controls
                      className="h-20 w-32 rounded-md border bg-black"
                      src={assetUrl(fragment.video_path)}
                    />
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleGenerateFragment(fragment.id)}
                    >
                      Generar
                    </Button>
                  )}
                </CardContent>
                {fragmentJobIds[fragment.id] && (
                  <div className="px-3 pb-3">
                    <JobProgress jobId={fragmentJobIds[fragment.id]} />
                  </div>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
