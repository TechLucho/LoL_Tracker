import { useState } from 'react'
import { Clock, AlertTriangle } from 'lucide-react'
import { useHeatmapStats } from '../hooks/useHeatmapStats'

const DAYS = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']
const TIME_BLOCKS = ['Madrugada', 'Mañana', 'Tarde', 'Noche']
const TIME_LABELS: Record<string, string> = {
  Madrugada: '🌙 Madrugada (00-06)',
  Mañana: '☀️ Mañana (06-12)',
  Tarde: '🌤 Tarde (12-18)',
  Noche: '🌃 Noche (18-00)',
}

function winrateColor(wr: number, games: number): string {
  if (games === 0) return 'bg-[#0D0D12]'
  if (wr >= 70) return 'bg-emerald-500/80'
  if (wr >= 60) return 'bg-emerald-500/50'
  if (wr >= 50) return 'bg-emerald-500/25'
  if (wr >= 40) return 'bg-red-500/25'
  if (wr >= 30) return 'bg-red-500/50'
  return 'bg-red-500/80'
}

function winrateTextColor(wr: number, games: number): string {
  if (games === 0) return 'text-gray-700'
  if (wr >= 60) return 'text-emerald-300'
  if (wr >= 50) return 'text-emerald-200'
  if (wr >= 40) return 'text-red-200'
  return 'text-red-300'
}

function CellSkeleton() {
  return <div className="shimmer h-20 rounded-lg bg-gray-800/30" />
}

export default function HeatmapPage() {
  const { data: cells, isLoading, isError } = useHeatmapStats()
  const [hoveredCell, setHoveredCell] = useState<string | null>(null)

  const cellMap = new Map<string, { games_played: number; wins: number; losses: number; winrate: number }>()
  if (cells) {
    for (const c of cells) {
      cellMap.set(`${c.day_of_week}-${c.time_block}`, c)
    }
  }

  const totalGames = cells?.reduce((s, c) => s + c.games_played, 0) ?? 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-black uppercase tracking-wider text-purple-400">
          🕐 Horarios / Heatmap
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Detecta tus horas pico y las de fatiga. Juega cuando ganas, para cuando pierdes.
        </p>
      </div>

      {/* Summary Bar */}
      {!isLoading && !isError && cells && cells.length > 0 && (
        <div className="flex items-center gap-4 rounded-xl border border-gray-800 bg-[#14141C] px-4 py-3">
          <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
            Total
          </span>
          <span className="font-mono text-sm font-bold text-white">{totalGames} partidas</span>
          <span className="text-[10px] text-gray-600">·</span>
          <span className="text-[10px] text-gray-500">7 días × 4 bloques horarios</span>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-2">
          <div className="grid grid-cols-[100px_repeat(4,1fr)] gap-2">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="contents">
                <CellSkeleton />
                <CellSkeleton />
                <CellSkeleton />
                <CellSkeleton />
                <CellSkeleton />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-16">
          <AlertTriangle className="h-8 w-8 text-red-500/50" />
          <p className="mt-3 text-sm text-red-400">Error al cargar el heatmap</p>
          <p className="mt-1 text-xs text-gray-500">Asegúrate de que el backend esté corriendo.</p>
        </div>
      )}

      {/* Empty */}
      {!isLoading && !isError && totalGames === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <Clock className="h-8 w-8 text-gray-600" />
          <p className="mt-3 text-sm font-medium text-gray-300">No hay datos de horarios</p>
          <p className="mt-1 text-xs text-gray-500">Sincroniza partidas para generar el mapa de calor.</p>
        </div>
      )}

      {/* Heatmap Grid */}
      {!isLoading && !isError && cells && totalGames > 0 && (
        <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
          <div className="overflow-x-auto">
          {/* Column Headers */}
          <div className="mb-2 grid grid-cols-[72px_repeat(4,1fr)] min-w-[400px] gap-2">
            <div /> {/* empty corner */}
            {TIME_BLOCKS.map((tb) => (
              <div key={tb} className="text-center">
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                  {TIME_LABELS[tb]}
                </span>
              </div>
            ))}
          </div>

          {/* Rows */}
          <div className="space-y-2">
            {DAYS.map((dayLabel, dayIdx) => (
              <div key={dayIdx} className="grid grid-cols-[72px_repeat(4,1fr)] min-w-[400px] gap-2">
                {/* Day label */}
                <div className="flex items-center">
                  <span className="text-xs font-bold text-gray-400">{dayLabel}</span>
                </div>

                {/* Time block cells */}
                {TIME_BLOCKS.map((tb) => {
                  const key = `${dayIdx}-${tb}`
                  const cell = cellMap.get(key)
                  const games = cell?.games_played ?? 0
                  const wins = cell?.wins ?? 0
                  const losses = cell?.losses ?? 0
                  const wr = cell?.winrate ?? 0
                  const cellId = key

                  return (
                    <div
                      key={cellId}
                      className={`relative flex h-20 flex-col items-center justify-center rounded-lg border transition-all ${
                        games === 0
                          ? 'border-gray-800/50 bg-[#0D0D12]'
                          : `border-gray-700/50 ${winrateColor(wr, games)} cursor-pointer hover:scale-105 hover:border-gray-600`
                      }`}
                      onMouseEnter={() => setHoveredCell(cellId)}
                      onMouseLeave={() => setHoveredCell(null)}
                    >
                      {games > 0 ? (
                        <>
                          <span className={`font-mono text-lg font-black ${winrateTextColor(wr, games)}`}>
                            {wr.toFixed(0)}%
                          </span>
                          <span className="text-[9px] text-gray-400">
                            {wins}W – {losses}L
                          </span>
                          <span className="text-[8px] text-gray-600">
                            {games} game{games !== 1 ? 's' : ''}
                          </span>
                        </>
                      ) : (
                        <span className="text-[9px] text-gray-700">—</span>
                      )}

                      {/* Tooltip */}
                      {hoveredCell === cellId && games > 0 && (
                        <div className="absolute -top-16 left-1/2 z-50 w-40 -translate-x-1/2 rounded-lg border border-gray-700 bg-[#1A1A24] px-3 py-2 shadow-xl">
                          <p className="text-[11px] font-bold text-white">
                            {dayLabel} · {tb}
                          </p>
                          <p className={`font-mono text-sm font-black ${winrateTextColor(wr, games)}`}>
                            {wr.toFixed(1)}% winrate
                          </p>
                          <p className="text-[10px] text-gray-400">
                            {wins} victoria{wins !== 1 ? 's' : ''} · {losses} derrota{losses !== 1 ? 's' : ''}
                          </p>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
          </div>

          {/* Legend */}
          <div className="mt-4 flex items-center justify-center gap-4 border-t border-gray-800 pt-3">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-600">Leyenda:</span>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-red-500/80" />
              <span className="text-[9px] text-gray-500">{"< 40%"}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-red-500/25" />
              <span className="text-[9px] text-gray-500">40-50%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-[#0D0D12] border border-gray-800" />
              <span className="text-[9px] text-gray-500">Sin datos</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-emerald-500/25" />
              <span className="text-[9px] text-gray-500">50-60%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-emerald-500/80" />
              <span className="text-[9px] text-gray-500">{"> 70%"}</span>
            </div>
          </div>
        </div>
      )}

      {/* Tip */}
      {!isLoading && !isError && cells && totalGames > 0 && (() => {
        const bestCell = cells.reduce(
          (best, c) => (c.games_played >= 2 && c.winrate > (best?.winrate ?? -1)) ? c : best,
          cells[0],
        )
        const worstCell = cells.reduce(
          (worst, c) => (c.games_played >= 2 && c.winrate < (worst?.winrate ?? 101)) ? c : worst,
          cells[0],
        )
        if (!bestCell || !worstCell) return null
        return (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                🏆 Mejor Horario
              </span>
              <p className="mt-1 text-sm font-bold text-white">
                {DAYS[bestCell.day_of_week]} · {bestCell.time_block}
              </p>
              <p className="text-xs text-gray-400">
                {bestCell.winrate.toFixed(1)}% WR en {bestCell.games_played} partidas
              </p>
            </div>
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-red-400">
                ⚠️ Peor Horario
              </span>
              <p className="mt-1 text-sm font-bold text-white">
                {DAYS[worstCell.day_of_week]} · {worstCell.time_block}
              </p>
              <p className="text-xs text-gray-400">
                {worstCell.winrate.toFixed(1)}% WR en {worstCell.games_played} partidas
              </p>
            </div>
          </div>
        )
      })()}
    </div>
  )
}
