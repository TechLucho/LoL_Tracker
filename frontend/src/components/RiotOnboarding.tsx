import { useState, type FormEvent } from 'react'
import { Swords } from 'lucide-react'
import { isAxiosError } from 'axios'
import { toast } from 'sonner'
import { useSettings, useLinkRiot } from '../hooks/useSettings'

// Fallback local por si /api/config no sirve su lista; la fuente de verdad es el backend
// (`settings.regions`, claves de ROUTING_MAP) que el frontend recibe vía useSettings.
const REGION_KEYS = ['EUW1', 'NA1', 'KR', 'JP1']

export default function RiotOnboarding() {
  const { data: settings, isLoading } = useSettings()
  const linkMutation = useLinkRiot()

  const [riotId, setRiotId] = useState('')
  const [region, setRegion] = useState('EUW1')

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="shimmer h-6 w-48 rounded bg-card" />
      </div>
    )
  }

  const regions = settings?.regions ?? REGION_KEYS

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!riotId.includes('#')) {
      toast.error('Formato del Riot ID: usa "Nombre#TAG" (ej. Lucho#EUW)')
      return
    }
    linkMutation.mutate(
      { riot_id: riotId.trim(), region },
      {
        onError: (err) => {
          // 401 lo gestiona el interceptor global (cierra sesión y redirige); aquí solo se
          // habla de fallos reales de vinculación (422/5xx).
          const detail = isAxiosError(err)
            ? (err.response?.data as { detail?: string } | undefined)?.detail
            : undefined
          toast.error(detail ? `❌ ${detail}` : '❌ No se pudo vincular. Comprueba tu Riot ID y región.')
        },
      },
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-5 rounded-xl border border-border bg-card p-6">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-bold text-text-primary">
            <Swords className="h-5 w-5 text-accent-purple" />
            Vincula tu cuenta de Riot
          </h1>
          <p className="text-sm text-text-muted">
            Necesitamos tu Riot ID para sincronizar tus partidas clasificatorias y calcular tus
            estadísticas. Sin esto, la app no puede mostrar tus datos.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-secondary">
              Riot ID <span className="text-text-muted">(Nombre#TAG)</span>
            </span>
            <input
              type="text"
              required
              value={riotId}
              onChange={(e) => setRiotId(e.target.value)}
              placeholder="Lucho#EUW"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none transition-colors focus:border-accent-purple/50"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-secondary">Región</span>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-purple/50"
            >
              {regions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>

          <button
            type="submit"
            disabled={linkMutation.isPending}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-purple px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-accent-purple/20 transition-all hover:bg-accent-purple-dim active:scale-95 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500"
          >
            <Swords className={`h-3.5 w-3.5 ${linkMutation.isPending ? 'animate-spin' : ''}`} />
            {linkMutation.isPending ? 'Vinculando...' : 'Vincular cuenta'}
          </button>
        </form>
      </div>
    </div>
  )
}