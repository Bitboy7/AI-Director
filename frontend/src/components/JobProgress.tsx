import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Stamp, type StampTone } from '@/components/stamp'
import { cancelJob, getJob } from '@/lib/api'
import type { Job, JobStatus } from '@/types'

const STATUS_LABEL: Record<JobStatus, string> = {
  queued: 'En cola',
  running: 'Procesando',
  succeeded: 'Completado',
  failed: 'Fallido',
  cancelled: 'Cancelado',
}

const STATUS_TONE: Record<JobStatus, StampTone> = {
  queued: 'muted',
  running: 'active',
  succeeded: 'ok',
  failed: 'danger',
  cancelled: 'muted',
}

interface Props {
  jobId: number
  onRetry?: () => void
  onComplete?: (job: Job) => void
}

export default function JobProgress({ jobId, onRetry, onComplete }: Props) {
  const [job, setJob] = useState<Job | null>(null)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete
  const notified = useRef(false)

  useEffect(() => {
    let cancelled = false

    const poll = async () => {
      try {
        const current = await getJob(jobId)
        if (cancelled) return
        setJob(current)
        if (!['succeeded', 'failed', 'cancelled'].includes(current.status)) {
          window.setTimeout(poll, 1000)
        } else if (current.status === 'succeeded' && !notified.current) {
          notified.current = true
          onCompleteRef.current?.(current)
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
  const running = job.status === 'running'

  return (
    <div className="w-full space-y-3 rounded-xl border border-border bg-muted/20 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {running && (
            <span className="animate-pulse-dot size-1.5 rounded-full bg-pencil" aria-hidden="true" />
          )}
          <Stamp tone={STATUS_TONE[job.status] ?? 'muted'}>{STATUS_LABEL[job.status] ?? job.status}</Stamp>
        </div>
        <span className="timecode text-sm text-muted-foreground">{job.progress}%</span>
      </div>
      <Progress value={job.progress} />
      {job.error && (
        <p className="text-sm text-destructive" role="alert">
          {job.error}
        </p>
      )}
      <div className="flex items-center gap-2">
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
      {running && (
        <p className="text-xs text-muted-foreground">
          Progreso estimado según el uso de recursos del proceso.
        </p>
      )}
    </div>
  )
}