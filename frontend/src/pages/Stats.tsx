import { useEffect, useState } from 'react'
import { Activity, Coins, Clock, Hash } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { getStats, listProjects } from '@/lib/api'
import type { ApiCall, Project, StatsTotals } from '@/types'

const KIND_LABEL: Record<string, string> = {
  llm: 'Guion',
  image: 'Imagen',
  video: 'Video',
  tts: 'Voz',
}

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

export default function Stats() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [calls, setCalls] = useState<ApiCall[]>([])
  const [totals, setTotals] = useState<StatsTotals | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [kind, setKind] = useState<string>('all')
  const [error, setError] = useState<string | null>(null)

  const projectId = searchParams.get('project') ?? 'all'

  useEffect(() => {
    void listProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
  }, [])

  useEffect(() => {
    let cancelled = false
    void getStats({
      project_id: projectId === 'all' ? undefined : Number(projectId),
      kind: kind === 'all' ? undefined : kind,
      limit: 200,
    })
      .then((data) => {
        if (cancelled) return
        setCalls(data.calls)
        setTotals(data.totals)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'error cargando stats')
      })
    return () => {
      cancelled = true
    }
  }, [kind, projectId])

  const setProject = (value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value === 'all') next.delete('project')
    else next.set('project', value)
    setSearchParams(next)
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="slug mb-2">Consumo de IA</p>
          <h1 className="text-3xl font-semibold tracking-tight">Estadísticas</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Registro de cada generación por API: duración, modelo, tokens y coste estimado.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={projectId} onValueChange={(value) => value && setProject(value)}>
            <SelectTrigger className="w-56" aria-label="Proyecto">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los proyectos</SelectItem>
              {projects.map((project) => (
                <SelectItem key={project.id} value={String(project.id)}>
                  {project.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={kind} onValueChange={(value) => value && setKind(value)}>
            <SelectTrigger className="w-44" aria-label="Tipo">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="llm">Guion</SelectItem>
              <SelectItem value="image">Imagen</SelectItem>
              <SelectItem value="video">Video</SelectItem>
              <SelectItem value="tts">Voz</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <TotalCard icon={<Activity className="size-4" />} label="Peticiones" value={totals ? String(totals.count) : '—'} />
        <TotalCard icon={<Coins className="size-4" />} label="Coste estimado" value={totals ? formatCost(totals.cost_usd) : '—'} />
        <TotalCard
          icon={<Hash className="size-4" />}
          label="Tokens (in / out)"
          value={totals ? `${totals.input_tokens.toLocaleString()} / ${totals.output_tokens.toLocaleString()}` : '—'}
        />
        <TotalCard icon={<Clock className="size-4" />} label="Tiempo total" value={totals ? formatDuration(totals.duration_ms) : '—'} />
      </div>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Peticiones</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {calls.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              Aún no hay generaciones registradas.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-muted-foreground">
                  <tr className="[&>th]:px-4 [&>th]:py-2 [&>th]:font-medium">
                    <th>Fecha</th>
                    <th>Proyecto</th>
                    <th>Tipo</th>
                    <th>Proveedor</th>
                    <th>Modelo</th>
                    <th>Duración</th>
                    <th>Tokens</th>
                    <th className="text-right">Coste</th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call) => (
                    <tr key={call.id} className="border-b border-border/60 last:border-0">
                      <td className="timecode px-4 py-2 text-xs text-muted-foreground">
                        {new Date(call.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {projects.find((project) => project.id === call.project_id)?.name ?? '—'}
                      </td>
                      <td className="px-4 py-2">
                        <Badge variant={call.status === 'ok' ? 'secondary' : 'destructive'}>
                          {KIND_LABEL[call.kind] ?? call.kind}
                        </Badge>
                      </td>
                      <td className="px-4 py-2">{call.provider}</td>
                      <td className="px-4 py-2 text-muted-foreground">{call.model || '—'}</td>
                      <td className="timecode px-4 py-2">{formatDuration(call.duration_ms)}</td>
                      <td className="timecode px-4 py-2 text-muted-foreground">
                        {call.input_tokens || call.output_tokens
                          ? `${call.input_tokens} / ${call.output_tokens}`
                          : call.units
                            ? `${call.units} u.`
                            : '—'}
                      </td>
                      <td className="timecode px-4 py-2 text-right">{formatCost(call.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}

function TotalCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center gap-2 text-muted-foreground">
          {icon}
          <span className="slug">{label}</span>
        </div>
        <p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
      </CardContent>
    </Card>
  )
}
