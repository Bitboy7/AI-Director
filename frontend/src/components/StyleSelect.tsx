import { useEffect, useState } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { getStyles, type StyleOption } from '@/lib/api'

const NO_STYLE = '__none__'

interface Props {
  value: string
  onChange: (value: string) => void
  id?: string
  label?: string
  className?: string
}

export default function StyleSelect({ value, onChange, id, label, className }: Props) {
  const [styles, setStyles] = useState<StyleOption[]>([])

  useEffect(() => {
    let cancelled = false
    void getStyles()
      .then((items) => {
        if (!cancelled) setStyles(items)
      })
      .catch(() => {
        if (!cancelled) setStyles([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Select
      value={value || NO_STYLE}
      onValueChange={(next) => onChange(!next || next === NO_STYLE ? '' : next)}
    >
      <SelectTrigger id={id} aria-label={label ?? 'Estilo'} className={className}>
        <SelectValue placeholder="Elige un estilo" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NO_STYLE}>Sin estilo</SelectItem>
        {styles.map((style) => (
          <SelectItem key={style.id} value={style.id}>
            {style.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
