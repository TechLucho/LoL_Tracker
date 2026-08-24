import { AlertTriangle } from 'lucide-react'
import { useHealth } from '../hooks/useHealth'

export default function HealthBanner() {
  const { data, isError } = useHealth()

  // Backend caído: ni siquiera /api/health responde. Eso TAMBIÉN hay que mostrarlo.
  if (isError) {
    return (
      <div
        role="alert"
        className="flex items-center gap-2 border-b border-orange-500/30 bg-orange-500/15 px-4 py-2 text-xs font-medium text-orange-200"
      >
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>
          No se pudo contactar con el backend. Comprueba que la API está corriendo en{' '}
          <code className="font-bold">VITE_API_URL</code>.
        </span>
      </div>
    )
  }

  // Mientras carga o con todo sano no molestramos: el banner sólo existe cuando algo arde.
  if (!data || (data.status === 'ok' && data.warnings.length === 0)) {
    return null
  }

  const critical = data.status === 'degraded'

  return (
    <div
      role="alert"
      className={`flex items-start gap-2 border-b px-4 py-2 text-xs font-medium ${
        critical
          ? 'border-orange-500/30 bg-orange-500/15 text-orange-200'
          : 'border-amber-500/30 bg-amber-500/15 text-amber-200'
      }`}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex flex-col gap-0.5">
        <span className="font-bold">
          {critical ? 'Backend degradado' : 'Avisos de salud'}
        </span>
        {data.warnings.map((warning) => (
          <span key={warning}>{warning}</span>
        ))}
      </div>
    </div>
  )
}
