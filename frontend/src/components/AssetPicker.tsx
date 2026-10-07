import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { uploadReferenceImage } from '@/lib/api'
import type { ReferenceImage } from '@/types'

interface Props {
  variantId: number
  onUploaded: (image: ReferenceImage) => void
}

export default function AssetPicker({ variantId, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handlePick = async (file: File | undefined) => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const image = await uploadReferenceImage(variantId, file)
      onUploaded(image)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'falló la subida')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(event) => void handlePick(event.target.files?.[0])}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
      >
        {uploading ? 'Subiendo…' : 'Subir imagen de referencia'}
      </Button>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
