import { useChampionStats } from '../hooks/useChampionStats'
import { DDragon } from '../data/constants'

export default function ChampionPoolPage() {
  const { data: champions, isLoading, isError } = useChampionStats()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-black uppercase tracking-wider text-purple-400">
          🎯 Champion Pool
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Rendimiento agregado por campeón con tus partidas sincronizadas.
        </p>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
            <span className="text-xs text-gray-500">Cargando estadísticas...</span>
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-16">
          <span className="text-2xl">⚠️</span>
          <p className="mt-2 text-sm text-red-400">Error al cargar campeones</p>
          <p className="mt-1 text-xs text-gray-500">Asegúrate de que el backend esté corriendo.</p>
        </div>
      )}

      {/* Empty */}
      {!isLoading && !isError && champions && champions.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <span className="text-3xl">🎮</span>
          <p className="mt-3 text-sm font-medium text-gray-300">No hay datos de campeones</p>
          <p className="mt-1 text-xs text-gray-500">Sincroniza partidas primero para ver estadísticas.</p>
        </div>
      )}

      {/* Champion Cards */}
      {!isLoading && !isError && champions && champions.length > 0 && (
        <div className="space-y-2">
          {champions.map((c) => {
            const losses = c.games_played - c.wins
            const wr = c.winrate
            const kdaColor =
              c.kda_ratio >= 5 ? 'text-orange-400' :
              c.kda_ratio >= 3 ? 'text-emerald-400' :
              c.kda_ratio >= 2 ? 'text-white' :
              'text-gray-400'
            const wrColor =
              wr >= 60 ? 'bg-emerald-500' :
              wr >= 50 ? 'bg-emerald-500/70' :
              wr >= 40 ? 'bg-yellow-500/70' :
              'bg-red-500/70'
            const wrTextColor =
              wr >= 60 ? 'text-emerald-400' :
              wr >= 50 ? 'text-emerald-300' :
              wr >= 40 ? 'text-yellow-400' :
              'text-red-400'

            return (
              <div
                key={c.champion}
                className="flex items-center gap-4 rounded-xl border border-gray-800 bg-[#14141C] px-4 py-3 transition-colors hover:bg-[#1A1A24]"
              >
                {/* Champion Icon + Name */}
                <div className="flex min-w-[140px] items-center gap-3">
                  <img
                    src={DDragon.champion(c.champion)}
                    alt={c.champion}
                    className="h-11 w-11 rounded-lg border border-gray-700"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                    }}
                  />
                  <div>
                    <span className="text-sm font-bold text-white">{c.champion}</span>
                    <p className="text-[10px] text-gray-500">
                      {c.games_played} game{c.games_played !== 1 ? 's' : ''}
                    </p>
                  </div>
                </div>

                {/* Winrate Bar */}
                <div className="min-w-[160px] flex-1">
                  <div className="mb-1 flex items-center justify-between">
                    <span className={`font-mono text-sm font-black ${wrTextColor}`}>
                      {wr.toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-gray-500">
                      {c.wins}W – {losses}L
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
                    <div
                      className={`h-full rounded-full ${wrColor} transition-all`}
                      style={{ width: `${Math.min(wr, 100)}%` }}
                    />
                  </div>
                </div>

                {/* KDA */}
                <div className="min-w-[80px] text-center">
                  <span className={`font-mono text-lg font-black ${kdaColor}`}>
                    {c.kda_ratio.toFixed(2)}
                  </span>
                  <p className="text-[10px] text-gray-500">KDA</p>
                  <p className="text-[9px] text-gray-600">
                    {c.avg_kills}/{c.avg_deaths}/{c.avg_assists}
                  </p>
                </div>

                {/* CS/min */}
                <div className="min-w-[70px] text-center">
                  <span className="font-mono text-sm font-bold text-white">
                    {c.avg_cs_min.toFixed(1)}
                  </span>
                  <p className="text-[10px] text-gray-500">CS/min</p>
                </div>

                {/* DPM */}
                <div className="min-w-[60px] text-center">
                  <span className="font-mono text-sm font-bold text-white">
                    {c.avg_dpm}
                  </span>
                  <p className="text-[10px] text-gray-500">DPM</p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
