import { AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import type { SessionFatigue } from '../api/client'

interface Props {
  data: SessionFatigue | undefined
  isLoading?: boolean
}

export default function SessionFatigueCard({ data, isLoading = false }: Props) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-hairline bg-surface-1 p-6">
        <div className="shimmer h-14 rounded-lg bg-surface-2/30" />
      </div>
    )
  }

  if (!data || (!data.sample_ok && !data.recent)) return null

  const Icon = data.fatigue_detected
    ? AlertTriangle
    : data.sample_ok
      ? CheckCircle2
      : Info

  const borderClass = data.fatigue_detected
    ? 'border-red-500/40'
    : data.sample_ok
      ? 'border-emerald-500/20'
      : 'border-blue-500/20'

  const bgClass = data.fatigue_detected
    ? 'bg-red-500/[0.06]'
    : data.sample_ok
      ? 'bg-emerald-500/[0.04]'
      : 'bg-blue-500/[0.04]'

  const iconColor = data.fatigue_detected
    ? 'text-red-400'
    : data.sample_ok
      ? 'text-emerald-400'
      : 'text-blue-400'

  const title = data.fatigue_detected
    ? 'Autopilot Detectado'
    : data.sample_ok
      ? 'Sesión Estable'
      : 'Estado de Sesión'

  return (
    <div className={`rounded-xl border ${borderClass} ${bgClass} p-4`}>
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 shrink-0 ${iconColor}`} />
        <span className="text-xs font-bold uppercase tracking-widest text-text-body">
          ⚡ {title}
        </span>
        {data.recent && data.previous && (
          <span className="ml-auto text-xs text-text-mute">
            {data.recent.wins}W-{data.recent.losses}L reciente
          </span>
        )}
      </div>
      <p className="mt-2 text-xs leading-relaxed text-text-mute">{data.message}</p>
      {data.sample_ok && data.winrate_delta_pp != null && data.kda_delta != null && (
        <div className="mt-2 flex gap-3 text-xs text-text-mute">
          <span>
            WR Δ{' '}
            <span
              className={`font-mono font-bold ${
                data.winrate_delta_pp <= 0 ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {data.winrate_delta_pp >= 0 ? '+' : ''}
              {data.winrate_delta_pp.toFixed(0)}pp
            </span>
          </span>
          <span>
            KDA Δ{' '}
            <span
              className={`font-mono font-bold ${
                data.kda_delta <= 0 ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {data.kda_delta >= 0 ? '+' : ''}
              {data.kda_delta.toFixed(1)}
            </span>
          </span>
        </div>
      )}
    </div>
  )
}
