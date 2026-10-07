import { useEffect, useState } from 'react'
import { ArrowLeft, CheckCircle2, Circle, Save, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  getCredentials,
  putCredentials,
  verifyCredential,
  type VerifyResult,
} from '@/lib/api'

const CATALOG = ['seedance', 'veo3', 'omni', 'openai', 'gemini', 'fal', 'elevenlabs', 'ollama', 'edge']

function StatusIcon({ status }: { status: VerifyResult['status'] | undefined }) {
  if (status === 'ok') {
    return (
      <span title="verificado">
        <CheckCircle2 className="size-4 text-ok" />
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span title="fallo">
        <XCircle className="size-4 text-destructive" />
      </span>
    )
  }
  const titles: Record<string, string> = {
    unavailable: 'no verificable',
    not_needed: 'no requiere clave',
    mock: 'proveedor simulado',
  }
  return (
    <span title={titles[status ?? ''] ?? 'sin verificar'}>
      <Circle className="size-4 text-muted-foreground" />
    </span>
  )
}

export default function Settings() {
  const [credentials, setCredentials] = useState<Record<string, Record<string, string>>>({})
  const [statuses, setStatuses] = useState<Record<string, VerifyResult>>({})
  const navigate = useNavigate()

  const refresh = async () => {
    setCredentials(await getCredentials())
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    for (const provider of CATALOG) {
      void verifyCredential(provider)
        .then((result) => setStatuses((prev) => ({ ...prev, [provider]: result })))
        .catch(() => setStatuses((prev) => ({ ...prev, [provider]: { status: 'error', detail: 'no se pudo verificar' } })))
    }
  }, [])

  const handleSave = async (provider: string, values: Record<string, string>) => {
    await putCredentials(provider, values)
    await refresh()
  }

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex items-start gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)} aria-label="Volver">
          <ArrowLeft className="size-4" />
        </Button>
        <div>
          <p className="slug mb-2">Configuración</p>
          <h1 className="text-2xl font-semibold tracking-tight">Configuración</h1>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            API keys y endpoints de los proveedores de IA. El check azul indica que la
            credencial está asignada y verificada en funcionamiento.
          </p>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {CATALOG.map((provider) => (
          <ProviderCard
            key={provider}
            provider={provider}
            values={credentials[provider] ?? {}}
            status={statuses[provider]}
            onSave={(values) => void handleSave(provider, values)}
          />
        ))}
      </div>
    </main>
  )
}

interface CardProps {
  provider: string
  values: Record<string, string>
  status: VerifyResult | undefined
  onSave: (values: Record<string, string>) => void
}

function ProviderCard({ provider, values, status, onSave }: CardProps) {
  const [apiKey, setApiKey] = useState('')
  const [endpoint, setEndpoint] = useState('')

  useEffect(() => {
    setApiKey(values.api_key ?? '')
    setEndpoint(values.endpoint ?? '')
  }, [values])

  const save = () => {
    const cleaned: Record<string, string> = {}
    if (apiKey.trim()) cleaned.api_key = apiKey.trim()
    if (endpoint.trim()) cleaned.endpoint = endpoint.trim()
    onSave(cleaned)
  }

  const hasStored = Object.values(values).some((value) => value.trim() !== '')

  return (
    <Card className="group transition-colors hover:border-border/60">
      <CardHeader>
        <CardTitle>
          <span className="slug mb-1 block text-[0.625rem]">Proveedor</span>
          <span className="font-mono text-sm font-medium tracking-tight">{provider}</span>
        </CardTitle>
        <div data-slot="card-action">
          <StatusIcon status={status?.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <Input
          type="password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          placeholder="API key"
          aria-label={`${provider} api_key`}
        />
        <Input
          value={endpoint}
          onChange={(event) => setEndpoint(event.target.value)}
          placeholder="endpoint (opcional)"
          aria-label={`${provider} endpoint`}
        />
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={save}>
            <Save />
            Guardar
          </Button>
          {hasStored && (
            <Button size="sm" variant="ghost" onClick={() => onSave({})}>
              Borrar credenciales
            </Button>
          )}
        </div>
        {status?.detail && status.status === 'ok' && (
          <p className="text-xs text-ok">{status.detail}</p>
        )}
        {status?.detail && status.status !== 'ok' && (
          <p className="text-xs text-muted-foreground">{status.detail}</p>
        )}
      </CardContent>
    </Card>
  )
}