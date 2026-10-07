import { assetUrl } from '@/lib/api'

interface Props {
  path?: string | null
  src?: string | null
  title?: string
}

export default function VideoPlayer({ path, src, title }: Props) {
  const source = src ?? (path ? assetUrl(path) : null)
  if (!source) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-md border bg-muted text-sm text-muted-foreground">
        Sin video
      </div>
    )
  }
  return (
    <video
      controls
      className="aspect-video w-full rounded-md border bg-black"
      src={source}
      title={title}
    />
  )
}
