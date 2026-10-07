import { useMemo, useRef, useState } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import type { Resource, ResourceType } from '@/types'

const TYPE_LABEL: Record<ResourceType, string> = {
  character: 'Personajes',
  scene: 'Escenas',
  prop: 'Utilería',
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function renderMentions(value: string, names: string[]) {
  if (!value || names.length === 0) return value
  const pattern = new RegExp(`@(${names.map(escapeRegExp).join('|')})`, 'gi')
  const nodes: React.ReactNode[] = []
  let last = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(value)) !== null) {
    if (match.index > last) nodes.push(value.slice(last, match.index))
    nodes.push(
      <mark key={`${match.index}-${match[1]}`} className="mention">
        @{match[1]}
      </mark>,
    )
    last = match.index + match[0].length
  }
  if (last < value.length) nodes.push(value.slice(last))
  return nodes
}

interface Props {
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  resources: Resource[]
  rows?: number
  className?: string
  ariaLabel?: string
}

export default function MentionTextarea({
  value,
  onChange,
  onBlur,
  resources,
  rows = 2,
  className,
  ariaLabel,
}: Props) {
  const ref = useRef<HTMLTextAreaElement | null>(null)
  const backdropRef = useRef<HTMLDivElement | null>(null)
  const [query, setQuery] = useState<string | null>(null)
  const [tab, setTab] = useState<ResourceType>('character')
  const [focused, setFocused] = useState(false)

  const names = useMemo(
    () =>
      resources
        .map((resource) => resource.name)
        .filter(Boolean)
        .sort((a, b) => b.length - a.length),
    [resources],
  )

  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = event.target.value
    onChange(next)
    const caret = event.target.selectionStart ?? next.length
    const match = /(?:^|\s)@([^@\s]*)$/.exec(next.slice(0, caret))
    setQuery(match ? match[1] : null)
  }

  const syncScroll = () => {
    const element = ref.current
    const backdrop = backdropRef.current
    if (!element || !backdrop) return
    backdrop.scrollTop = element.scrollTop
    backdrop.scrollLeft = element.scrollLeft
  }

  const insert = (name: string) => {
    const element = ref.current
    const caret = element?.selectionStart ?? value.length
    const before = value.slice(0, caret)
    const after = value.slice(caret)
    const match = /(?:^|\s)@([^@\s]*)$/.exec(before)
    const start = match ? caret - match[1].length - 1 : caret
    const next = `${value.slice(0, start)}@${name} ${after}`
    onChange(next)
    setQuery(null)
    const pos = start + name.length + 2
    window.requestAnimationFrame(() => {
      element?.focus()
      element?.setSelectionRange(pos, pos)
    })
  }

  const filtered = useMemo(
    () =>
      resources.filter(
        (resource) =>
          resource.type === tab &&
          (!query || resource.name.toLowerCase().includes(query.toLowerCase())),
      ),
    [resources, tab, query],
  )

  return (
    <div className="relative">
      {!focused && (
        <div
          ref={backdropRef}
          aria-hidden="true"
          className={cn(
            'pointer-events-none absolute inset-px overflow-hidden rounded-lg px-2.5 py-2 break-words whitespace-pre-wrap',
            className,
          )}
        >
          {renderMentions(value, names)}
        </div>
      )}
      <Textarea
        ref={ref}
        value={value}
        onChange={handleChange}
        onScroll={syncScroll}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false)
          onBlur?.()
        }}
        rows={rows}
        aria-label={ariaLabel}
        spellCheck={false}
        className={cn(
          'relative dark:bg-transparent',
          !focused && 'text-transparent',
          className,
        )}
        placeholder="Escribe @ para mencionar personajes, escenas o utilería"
      />
      {query !== null && (
        <div className="absolute z-30 mt-1 w-full rounded-lg border border-border bg-popover p-2 shadow-lg">
          <Tabs value={tab} onValueChange={(next) => setTab(next as ResourceType)}>
            <TabsList className="w-full">
              {(['character', 'scene', 'prop'] as ResourceType[]).map((type) => (
                <TabsTrigger key={type} value={type} className="text-xs">
                  {TYPE_LABEL[type]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <p className="slug mt-2 px-1">Filtro: {query || '—'}</p>
          <div className="mt-1 max-h-40 overflow-auto">
            {filtered.length === 0 ? (
              <p className="p-2 text-xs text-muted-foreground">Sin resultados</p>
            ) : (
              filtered.map((resource) => (
                <button
                  key={resource.id}
                  type="button"
                  className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-muted"
                  onMouseDown={(event) => {
                    event.preventDefault()
                    insert(resource.name)
                  }}
                >
                  {resource.name}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
