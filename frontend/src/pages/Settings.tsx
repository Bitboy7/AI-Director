import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  getCredentials,
  putCredentials,
  verifyCredential,
  type VerifyResult,
} from '@/lib/api'

const CATALOG = ['seedance', 'veo3', 'omni', 'openai', 'gemini', 'elevenlabs', 'ollama', 'edge']

function StatusIcon({ status }: { status: VerifyResult['status'] | undefined }) {
  if (status === 'ok') {
    return (
      <span title="verificado">
        <CheckCircle2 className="size-4 text-green-500" />
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span title="fallo">
        <XCircle className="size-4 text-red-500" />
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
    <main className="mx-auto max-w-4xl p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight">Configuración</h2>
        <p className="text-sm text-muted-foreground">
          API keys y endpoints de los proveedores de IA. El check verde indica que la
          credencial está asignada y verificada en funcionamiento.
        </p>
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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{provider}</span>
          <StatusIcon status={status?.status} />
        </CardTitle>
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
            Guardar
          </Button>
          {hasStored && (
            <Button size="sm" variant="ghost" onClick={() => onSave({})}>
              Borrar credenciales
            </Button>
          )}
        </div>
        {status?.detail && status.status === 'ok' && (
          <p className="text-xs text-green-600">{status.detail}</p>
        )}
        {status?.detail && status.status !== 'ok' && (
          <p className="text-xs text-muted-foreground">{status.detail}</p>
        )}
      </CardContent>
    </Card>
  )
}
