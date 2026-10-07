import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Coins } from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  getProviderModels,
  getProviders,
  getResolutions,
  type ProviderModel,
  type ProviderOption,
  type ResolutionOption,
} from '@/lib/api'
import { cn } from '@/lib/utils'

type ProviderKind = 'llm' | 'image' | 'video' | 'tts'

interface Props {
  kind: ProviderKind
  value: string
  label: string
  onChange: (value: string) => void
  model?: string
  onModelChange?: (model: string) => void
  resolution?: string | null
  onResolutionChange?: (resolution: string) => void
  aspect?: string
  durationSeconds?: number
  providers?: ProviderOption[]
  dense?: boolean
  className?: string
}

function formatUsd(value: number): string {
  if (value >= 1) return `$${value.toFixed(2)}`
  return `$${value.toFixed(3)}`
}

function priceHint(kind: ProviderKind, pricing: ProviderModel['pricing']): string | null {
  if (!pricing) return null
  if (kind === 'video' && pricing.unit === 'second' && pricing.usd) {
    return `${formatUsd(pricing.usd)}/s`
  }
  if (kind === 'image' && pricing.unit === 'image' && pricing.usd) {
    return `${formatUsd(pricing.usd)}/img`
  }
  if (kind === 'llm' && pricing.unit === '1m_tokens') {
    return `${formatUsd(pricing.input ?? 0)} in`
  }
  return null
}

function estimateLabel(
  kind: ProviderKind,
  pricing: ProviderModel['pricing'],
  durationSeconds: number | undefined,
): string | null {
  if (!pricing) return null
  if (kind === 'video' && pricing.unit === 'second' && pricing.usd) {
    return `≈ ${formatUsd(pricing.usd * (durationSeconds ?? 10))} · ${durationSeconds ?? 10}s`
  }
  if (kind === 'image' && pricing.unit === 'image' && pricing.usd) {
    return `${formatUsd(pricing.usd)} / imagen`
  }
  if (kind === 'llm' && pricing.unit === '1m_tokens') {
    return `${formatUsd(pricing.input ?? 0)} / ${formatUsd(pricing.output ?? 0)} por 1M`
  }
  return null
}

function Field({
  label,
  children,
  dense,
  className,
}: {
  label: string
  children: ReactNode
  dense?: boolean
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-1', dense && 'gap-0.5', className)}>
      <span className="slug leading-none">{label}</span>
      {children}
    </div>
  )
}

export default function ProviderSelector({
  kind,
  value,
  label,
  onChange,
  model,
  onModelChange,
  resolution,
  onResolutionChange,
  aspect = '16:9',
  durationSeconds,
  providers,
  dense,
  className,
}: Props) {
  const [options, setOptions] = useState<ProviderOption[]>(providers ?? [])
  const [models, setModels] = useState<ProviderModel[]>([])
  const [resolutions, setResolutions] = useState<ResolutionOption[]>([])

  useEffect(() => {
    if (providers) {
      setOptions(providers)
      return
    }
    let cancelled = false
    void getProviders()
      .then((catalog) => {
        if (!cancelled) setOptions(catalog[kind] ?? [])
      })
      .catch(() => {
        if (!cancelled) setOptions([])
      })
    return () => {
      cancelled = true
    }
  }, [kind, providers])

  useEffect(() => {
    let cancelled = false
    setModels([])
    void getProviderModels(kind, value)
      .then((items) => {
        if (!cancelled) setModels(items)
      })
      .catch(() => {
        if (!cancelled) setModels([])
      })
    return () => {
      cancelled = true
    }
  }, [kind, value])

  const wantsResolution = onResolutionChange != null
  useEffect(() => {
    if (!wantsResolution) return
    let cancelled = false
    void getResolutions(kind, value, { model: model || undefined, aspect })
      .then((items) => {
        if (!cancelled) setResolutions(items)
      })
      .catch(() => {
        if (!cancelled) setResolutions([])
      })
    return () => {
      cancelled = true
    }
  }, [kind, value, model, aspect, wantsResolution])

  const visible = options.filter((option) => option.configured || option.name === value)
  const items = visible.length > 0 ? visible.map((option) => option.name) : value ? [value] : []
  const showModelSelect = onModelChange != null && models.length > 0

  const resolutionItems = useMemo(() => {
    const mapped = resolutions.map((item) => ({ label: item.label, value: item.value ?? item.label }))
    if (resolution && !mapped.some((item) => item.value === resolution)) {
      mapped.unshift({ label: resolution, value: resolution })
    }
    return mapped
  }, [resolutions, resolution])

  const selectedModel = models.find((item) => item.id === model)
  const estimate =
    showModelSelect && selectedModel
      ? estimateLabel(kind, selectedModel.pricing, durationSeconds)
      : null

  return (
    <div className={cn('flex flex-wrap items-end gap-2.5', className)}>
      <Field label={label} dense={dense}>
        <Select value={value ?? ''} onValueChange={(next) => next && onChange(next)}>
          <SelectTrigger
            aria-label={label}
            size={dense ? 'sm' : 'default'}
            className={dense ? 'w-40' : 'w-48'}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {items.map((name) => (
              <SelectItem key={name} value={name}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      {showModelSelect && (
        <Field label="Modelo" dense={dense}>
          <Select value={model ?? ''} onValueChange={(next) => next && onModelChange(next)}>
            <SelectTrigger
              aria-label={`${label} (modelo)`}
              size={dense ? 'sm' : 'default'}
              className={dense ? 'w-72' : 'w-[26rem]'}
            >
              <SelectValue placeholder="Modelo" />
            </SelectTrigger>
            <SelectContent className="min-w-[26rem] max-w-[92vw]">
              {models.map((m) => {
                const hint = priceHint(kind, m.pricing)
                return (
                  <SelectItem key={m.id} value={m.id}>
                    <span className="flex w-full items-center justify-between gap-4">
                      <span className="whitespace-nowrap">{m.name}</span>
                      {hint && (
                        <span className="timecode text-[0.65rem] text-muted-foreground">
                          {hint}
                        </span>
                      )}
                    </span>
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
        </Field>
      )}

      {onResolutionChange && resolutionItems.length > 0 && (
        <Field label="Resolución" dense={dense}>
          <Select
            value={resolution ?? ''}
            onValueChange={(next) => next && onResolutionChange(next)}
          >
            <SelectTrigger
              aria-label={`${label} (resolución)`}
              size={dense ? 'sm' : 'default'}
              className={dense ? 'w-44' : 'w-48'}
            >
              <SelectValue placeholder="Resolución" />
            </SelectTrigger>
            <SelectContent>
              {resolutionItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}

      {estimate && (
        <span
          className="timecode inline-flex h-7 items-center gap-1 rounded-md border border-pencil/30 bg-pencil/10 px-2 text-[0.7rem] text-pencil"
          title="Coste estimado"
        >
          <Coins className="size-3" />
          {estimate}
        </span>
      )}
    </div>
  )
}
