import { useMemo } from 'react'
import { Aperture } from 'lucide-react'

interface Mote {
  id: number
  left: number
  size: number
  delay: number
  duration: number
  drift: number
  opacity: number
}

function hash(seed: number): number {
  const value = Math.sin(seed * 12.9898) * 43758.5453
  return value - Math.floor(value)
}

interface Props {
  episodeNumber: number
  title: string
}

export function RenderCurtain({ episodeNumber, title }: Props) {
  const motes = useMemo<Mote[]>(
    () =>
      Array.from({ length: 30 }, (_, id) => ({
        id,
        left: hash(id * 3 + 1) * 100,
        size: 2 + hash(id * 3 + 2) * 4,
        delay: hash(id * 3 + 3) * 3,
        duration: 2.6 + hash(id * 7 + 5) * 2.6,
        drift: (hash(id * 7 + 6) - 0.5) * 46,
        opacity: 0.35 + hash(id * 7 + 7) * 0.55,
      })),
    [],
  )

  return (
    <div
      data-slot="render-curtain"
      className="absolute inset-0 z-10 flex flex-col items-center justify-center overflow-hidden rounded-md border border-pencil/30 bg-[oklch(0.09_0.02_262)]"
    >
      <span aria-hidden="true" className="render-glow" />
      <span aria-hidden="true" className="render-sweep" />
      {motes.map((mote) => (
        <span
          key={mote.id}
          aria-hidden="true"
          className="render-mote"
          style={
            {
              left: `${mote.left}%`,
              width: mote.size,
              height: mote.size,
              animationDelay: `${mote.delay}s`,
              animationDuration: `${mote.duration}s`,
              '--drift': `${mote.drift}px`,
              '--mote-opacity': mote.opacity,
            } as React.CSSProperties
          }
        />
      ))}
      <div className="relative z-10 flex flex-col items-center gap-3 px-6 text-center">
        <span className="relative flex size-14 items-center justify-center">
          <span className="absolute inset-0 animate-ping rounded-full bg-pencil/20" aria-hidden="true" />
          <span className="relative flex size-11 items-center justify-center rounded-full border border-pencil/50 bg-pencil/10 text-pencil shadow-[0_0_30px_-4px_color-mix(in_oklch,var(--pencil)_60%,transparent)]">
            <Aperture className="size-5" />
          </span>
        </span>
        <p className="slug text-pencil">Renderizando capítulo</p>
        <p className="timecode text-xs text-muted-foreground">
          Cap. {String(episodeNumber).padStart(2, '0')}
          {title ? ` · ${title}` : ''}
        </p>
      </div>
    </div>
  )
}

export function RenderFlash() {
  return (
    <span
      aria-hidden="true"
      className="render-flash pointer-events-none absolute inset-0 z-20 rounded-md"
    />
  )
}
