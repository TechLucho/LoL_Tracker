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
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <div className="shimmer h-6 w-48 rounded bg-surface-1" />
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
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-md space-y-5 rounded-xl border border-hairline bg-surface-1 p-6">
        <div className="space-y-1">
          <p className="text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
            Paso 1 · Vinculación
          </p>
          <h1 className="flex items-center gap-2 text-lg font-bold text-text-ink">
            <Swords className="h-5 w-5 text-accent-primary" />
            Vincula tu cuenta de Riot
          </h1>
          <p className="text-sm text-text-mute">
            Necesitamos tu Riot ID para sincronizar tus partidas clasificatorias y calcular tus
            estadísticas. Sin esto, la app no puede mostrar tus datos.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-body">
              Riot ID <span className="text-text-mute">(Nombre#TAG)</span>
            </span>
            <input
              type="text"
              required
              value={riotId}
              onChange={(e) => setRiotId(e.target.value)}
              placeholder="Lucho#EUW"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm text-text-ink placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-body">Región</span>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm text-text-ink outline-none transition-colors focus:border-accent-primary/50"
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
            className="flex w-full items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-3 text-sm font-bold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute"
          >
            <Swords className={`h-3.5 w-3.5 ${linkMutation.isPending ? 'animate-spin' : ''}`} />
            {linkMutation.isPending ? 'Vinculando...' : 'Vincular cuenta'}
          </button>
        </form>
      </div>
    </div>
  )
}