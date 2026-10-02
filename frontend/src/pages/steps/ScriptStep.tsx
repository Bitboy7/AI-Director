import { useEffect, useState } from 'react'
import JobProgress from '@/components/JobProgress'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { generateScript, listEpisodes } from '@/lib/api'
import type { Episode, Project } from '@/types'

interface Props {
  project: Project
}

export default function ScriptStep({ project }: Props) {
  const [synopsis, setSynopsis] = useState(project.synopsis)
  const [videoStyle, setVideoStyle] = useState(project.video_style)
  const [numEpisodes, setNumEpisodes] = useState(1)
  const [duration, setDuration] = useState(90)
  const [jobId, setJobId] = useState<number | null>(null)
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setEpisodes(await listEpisodes(project.id))
  }

  useEffect(() => {
    void refresh()
  }, [project.id])

  const handleGenerate = async () => {
    setError(null)
    try {
      const job = await generateScript(project.id, {
        synopsis,
        video_style: videoStyle,
        num_episodes: numEpisodes,
        episode_duration_seconds: duration,
      })
      setJobId(job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error al generar el guion')
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Generar guion con IA</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="synopsis">Sinopsis</Label>
            <Textarea
              id="synopsis"
              value={synopsis}
              onChange={(event) => setSynopsis(event.target.value)}
              rows={4}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label htmlFor="style">Estilo</Label>
              <Input
                id="style"
                value={videoStyle}
                onChange={(event) => setVideoStyle(event.target.value)}
              />
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
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button onClick={() => void handleGenerate()} disabled={!synopsis.trim()}>
            Generar guion
          </Button>
          {jobId && (
            <JobProgress
              key={jobId}
              jobId={jobId}
              onRetry={() => void handleGenerate()}
            />
          )}
        </CardContent>
      </Card>

      {episodes.map((episode) => (
        <Card key={episode.id}>
          <CardHeader>
            <CardTitle>
              Episodio {episode.number}: {episode.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {episode.fragments.map((fragment) => (
              <div key={fragment.id} className="rounded-md border p-3">
                <p className="text-sm font-medium">
                  [{episode.number}-{fragment.shot_number}] {fragment.time_place}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">{fragment.prompt_video}</p>
                {fragment.dialogue_lines.map((line) => (
                  <p key={line.id} className="mt-1 text-sm italic">
                    — {line.text}
                  </p>
                ))}
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
