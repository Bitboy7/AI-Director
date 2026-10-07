import { Check } from 'lucide-react'

import { cn } from '@/lib/utils'

export type StampTone = 'ok' | 'danger' | 'active' | 'pencil' | 'muted'

const toneClass: Record<StampTone, string> = {
  ok: 'border-ok/45 text-ok',
  danger: 'border-destructive/50 text-destructive',
  active: 'border-pencil/55 text-pencil',
  pencil: 'border-pencil/70 bg-pencil/10 text-pencil',
  muted: 'border-border text-muted-foreground',
}

export function Stamp({
  tone = 'muted',
  className,
  children,
}: {
  tone?: StampTone
  className?: string
  children: React.ReactNode
}) {
  return (
    <span
      className={cn(
        'animate-stamp-in inline-flex w-fit shrink-0 items-center gap-1 rounded-[0.2rem] border px-1.5 py-0.5 font-mono text-[0.625rem] leading-none font-medium tracking-[0.16em] uppercase',
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function DoneCheck({ className }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label="Completado"
      title="Completado"
      className={cn('inline-flex shrink-0 items-center text-ok', className)}
    >
      <Check className="size-4" strokeWidth={3} />
    </span>
  )
}