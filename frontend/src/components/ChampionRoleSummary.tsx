import { MapPin } from 'lucide-react'
import type { ChampionRoleSummary } from '../api/client'
import { DDragon } from '../data/constants'
import { useIcons } from '../hooks/useMetadata'

const QUEUE_NAMES: Record<number, string> = {
  420: 'Ranked',
  400: 'Normal',
  430: 'Blind',
  440: 'Flex',
  1020: 'ARAM',
  900: 'URF',
}

const ROLE_LABELS: Record<string, string> = {
  TOP: 'Top',
  JUNGLE: 'Jungle',
  MIDDLE: 'Mid',
  BOTTOM: 'Bot',
  UTILITY: 'Sup',
  Unknown: '???',
}

interface Props {
  rows: ChampionRoleSummary[]
  isLoading?: boolean
}

export default function ChampionRoleSummary({ rows, isLoading = false }: Props) {
  const icons = useIcons()

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-purple-400">
        📊 Resumen por Rol
      </h3>

      {isLoading && <div className="shimmer h-32 rounded-lg bg-gray-800/30" />}

      {!isLoading && rows.length === 0 && (
        <div className="flex flex-col items-center gap-1.5 py-4">
          <MapPin className="h-5 w-5 text-gray-600" />
          <p className="text-[11px] text-gray-500">
            Sin combinaciones con ≥3 partidas para desglosar.
          </p>
        </div>
      )}

      {rows.length > 0 && (
        <div className="space-y-1.5">
          {rows.slice(0, 8).map((r) => {
            const champIcon = icons.champion(r.champion)
            return (
              <div
                key={`${r.champion}-${r.role}-${r.queue_id}`}
                className="flex items-center gap-2.5 rounded-lg border border-gray-800/50 bg-[#0D0D12] px-2.5 py-2 transition-colors hover:bg-[#1A1A24]"
              >
                <img
                  src={champIcon.url}
                  alt={r.champion}
                  title={champIcon.name}
                  className="h-7 w-7 rounded-md border border-gray-700"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="truncate text-xs font-bold text-white">
                      {r.champion}
                    </span>
                    <span
                      className={`font-mono text-xs font-bold ${
                        r.winrate >= 60
                          ? 'text-emerald-400'
                          : r.winrate < 50
                            ? 'text-red-400'
                            : 'text-gray-400'
                      }`}
                    >
                      {r.winrate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[9px] text-gray-500">
                    <span className="rounded bg-gray-800 px-1 py-0.5 text-[8px] font-semibold uppercase text-gray-400">
                      {ROLE_LABELS[r.role] ?? r.role}
                    </span>
                    <span>{QUEUE_NAMES[r.queue_id] ?? `Q${r.queue_id}`}</span>
                    <span>·</span>
                    <span>{r.games_played}g</span>
                    <span>·</span>
                    <span className="font-mono">KDA {r.kda_ratio.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            )
          })}
          {rows.length > 8 && (
            <p className="text-center text-[9px] text-gray-600">
              +{rows.length - 8} combinaciones más
            </p>
          )}
        </div>
      )}
    </div>
  )
}
