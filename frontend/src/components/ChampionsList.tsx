import { Crosshair } from 'lucide-react'
import type { ChampionPerf } from '../api/client'
import { DDragon } from '../data/constants'
import { useIcons } from '../hooks/useMetadata'

// El sidebar no da para 17 campeones: top por partidas jugadas (la query ya ordena así).
const TOP_N = 8

interface Props {
  champions: ChampionPerf[]
  isLoading?: boolean
}

export default function ChampionsList({ champions, isLoading = false }: Props) {
  // Metadatos del backend (/api/metadata/champions): los stats agregan por nombre visible
  // ("Lee Sin"), que es exactamente la clave del índice por nombre de useIcons.
  const icons = useIcons()
  const visible = champions.slice(0, TOP_N)

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-purple-400">
        🎯 Champions
      </h3>

      {isLoading && <div className="shimmer h-24 rounded-lg bg-gray-800/30" />}

      {!isLoading && visible.length === 0 && (
        <div className="flex flex-col items-center gap-1.5 py-4">
          <Crosshair className="h-5 w-5 text-gray-600" />
          <p className="text-[11px] text-gray-500">
            Sincroniza partidas para ver el rendimiento de tus campeones.
          </p>
        </div>
      )}

      {visible.length > 0 && (
        <>
          <div className="flex flex-col gap-1.5">
            {visible.map((c) => (
              <div
                key={c.champion}
                className="flex items-center gap-3 rounded-lg border border-gray-800/50 bg-[#0D0D12] px-3 py-2 transition-colors hover:bg-[#1A1A24]"
              >
                <img
                  src={icons.champion(c.champion).url}
                  alt={c.champion}
                  title={icons.champion(c.champion).name}
                  className="h-9 w-9 rounded-lg border border-gray-700"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">{c.champion}</span>
                    <span className={`font-mono text-xs font-bold ${
                      c.winrate >= 60 ? 'text-emerald-400' : c.winrate < 50 ? 'text-red-400' : 'text-gray-400'
                    }`}>
                      {c.winrate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-gray-800">
                    <div
                      className={`h-full rounded-full transition-all ${
                        c.winrate >= 60 ? 'bg-emerald-500' : c.winrate < 50 ? 'bg-red-500' : 'bg-gray-600'
                      }`}
                      style={{ width: `${c.winrate}%` }}
                    />
                  </div>
                  <div className="mt-1.5 flex items-center gap-1.5 text-[9px] text-gray-500">
                    <span>{c.games_played}g · {c.wins}W-{c.games_played - c.wins}L</span>
                    <span>·</span>
                    <span>KDA {c.kda_ratio.toFixed(1)}</span>
                    <span>·</span>
                    {/* Daño real medio a campeones, calculado en el backend desde participants. */}
                    <span className={`font-mono font-bold ${c.avg_dpm >= 700 ? 'text-orange-400' : 'text-gray-500'}`}>
                      {Math.round(c.avg_dpm)} dpm
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {visible.length < champions.length && (
            <p className="mt-2 text-center text-[9px] text-gray-600">
              +{champions.length - visible.length} campeones con partidas
            </p>
          )}
        </>
      )}
    </div>
  )
}
