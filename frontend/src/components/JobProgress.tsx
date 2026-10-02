import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cancelJob, getJob } from '@/lib/api'
import type { Job, JobStatus } from '@/types'

const STATUS_LABEL: Record<JobStatus, string> = {
  queued: 'En cola',
  running: 'Procesando',
  succeeded: 'Completado',
  failed: 'Fallido',
  cancelled: 'Cancelado',
}

const STATUS_VARIANT: Record<JobStatus, 'secondary' | 'default' | 'destructive' | 'outline'> = {
  queued: 'secondary',
  running: 'default',
  succeeded: 'outline',
  failed: 'destructive',
  cancelled: 'outline',
}

interface Props {
  jobId: number
  onRetry?: () => void
}

export default function JobProgress({ jobId, onRetry }: Props) {
  const [job, setJob] = useState<Job | null>(null)

  useEffect(() => {
    let cancelled = false

    const poll = async () => {
      try {
        const current = await getJob(jobId)
        if (cancelled) return
        setJob(current)
        if (!['succeeded', 'failed', 'cancelled'].includes(current.status)) {
          window.setTimeout(poll, 1000)
        }
      } catch (error) {
        if (!cancelled) {
          setJob((prev) => prev ?? { error: String(error) } as Job)
        }
      }
    }
    poll()

    return () => {
      cancelled = true
    }
  }, [jobId])

  if (!job) return null

  const terminal = ['succeeded', 'failed', 'cancelled'].includes(job.status)

  return (
    <div className="w-full space-y-2 rounded-md border p-3">
      <div className="flex items-center justify-between gap-2">
        <Badge variant={STATUS_VARIANT[job.status] ?? 'secondary'}>
          {STATUS_LABEL[job.status] ?? job.status}
        </Badge>
        <span className="text-sm tabular-nums text-muted-foreground">{job.progress}%</span>
      </div>
      <Progress value={job.progress} />
      {job.error && (
        <p className="text-sm text-destructive" role="alert">
          {job.error}
        </p>
      )}
      {!terminal && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => void cancelJob(jobId)}
        >
          Cancelar
        </Button>
      )}
      {job.status === 'failed' && onRetry && (
        <Button size="sm" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  )
}
