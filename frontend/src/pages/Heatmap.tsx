import { useState } from 'react'
import { Clock, AlertTriangle } from 'lucide-react'
import { useHeatmapStats } from '../hooks/useHeatmapStats'
import type { HeatmapCell } from '../api/client'

// La cuadrícula ordena los días Lunes → Domingo (el backend codifica DOW con 0 = Domingo).
const DAY_COLUMNS: { label: string; dow: number }[] = [
  { label: 'Lun', dow: 1 },
  { label: 'Mar', dow: 2 },
  { label: 'Mié', dow: 3 },
  { label: 'Jue', dow: 4 },
  { label: 'Vie', dow: 5 },
  { label: 'Sáb', dow: 6 },
  { label: 'Dom', dow: 0 },
]

const DAY_NAMES = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

const TIME_BLOCKS = ['Madrugada', 'Mañana', 'Tarde', 'Noche']

// Escala térmica basada en winrate: verdes hacia la victoria, rojos hacia la derrota,
// neutro cuando la franja no tiene partidas.
function cellColor(wr: number, games: number): string {
  if (games === 0) return 'border-gray-800/40 bg-[#0D0D12]'
  if (wr >= 75) return 'border-emerald-400/40 bg-emerald-500/90'
  if (wr >= 65) return 'border-emerald-400/30 bg-emerald-500/65'
  if (wr >= 50) return 'border-emerald-400/20 bg-emerald-500/35'
  if (wr >= 40) return 'border-red-400/20 bg-red-500/35'
  if (wr >= 25) return 'border-red-400/30 bg-red-500/65'
  return 'border-red-400/40 bg-red-500/90'
}

function cellTextColor(wr: number, games: number): string {
  if (games === 0) return 'text-gray-700'
  if (wr >= 60) return 'text-emerald-100'
  if (wr >= 50) return 'text-emerald-200'
  if (wr >= 40) return 'text-red-200'
  return 'text-red-100'
}

function CellSkeleton() {
  return <div className="shimmer h-9 rounded-md bg-gray-800/30" />
}

function formatTooltip(cell: HeatmapCell): string {
  const day = DAY_NAMES[cell.day_of_week]
  return `${day} · ${cell.time_block}: ${cell.winrate.toFixed(0)}% WR (${cell.wins}V - ${cell.losses}D)`
}

export default function HeatmapPage() {
  const { data, isLoading, isError } = useHeatmapStats()
  const [hovered, setHovered] = useState<{ key: string; x: number; y: number } | null>(null)

  const cells = data?.cells ?? []
  const cellMap = new Map<string, HeatmapCell>()
  for (const c of cells) {
    cellMap.set(`${c.day_of_week}-${c.time_block}`, c)
  }

  const totalGames = cells.reduce((s, c) => s + c.games_played, 0)
  const bestSlot = data?.best_slot ?? null
  const worstSlot = data?.worst_slot ?? null

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
      {!isLoading && !isError && cells.length > 0 && (
        <div className="flex items-center gap-4 rounded-xl border border-gray-800 bg-[#14141C] px-4 py-3">
          <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
            Total
          </span>
          <span className="font-mono text-sm font-bold text-white">{totalGames} partidas</span>
          <span className="text-[10px] text-gray-600">·</span>
          <span className="text-[10px] text-gray-500">7 días × 4 franjas horarias</span>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-2">
          <div className="grid grid-cols-[56px_repeat(7,1fr)] gap-1.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="contents">
                <CellSkeleton />
                <CellSkeleton />
                <CellSkeleton />
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
      {!isLoading && !isError && cells.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
          <div className="overflow-x-auto">
            <div className="min-w-[480px]">
              {/* Column headers: días */}
              <div className="mb-1.5 grid grid-cols-[56px_repeat(7,1fr)] gap-1.5">
                <div />
                {DAY_COLUMNS.map((d) => (
                  <div key={d.dow} className="text-center">
                    <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500">
                      {d.label}
                    </span>
                  </div>
                ))}
              </div>

              {/* Filas: franjas horarias */}
              <div className="space-y-1.5">
                {TIME_BLOCKS.map((tb) => (
                  <div key={tb} className="grid grid-cols-[56px_repeat(7,1fr)] gap-1.5">
                    <div className="flex items-center">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500">
                        {tb}
                      </span>
                    </div>
                    {DAY_COLUMNS.map((d) => {
                      const key = `${d.dow}-${tb}`
                      const cell = cellMap.get(key)
                      const games = cell?.games_played ?? 0
                      const wr = cell?.winrate ?? 0

                      return (
                        <div
                          key={key}
                          className={`relative flex h-9 cursor-default items-center justify-center rounded-md border transition-transform ${
                            games > 0 ? 'hover:z-10 hover:scale-110' : ''
                          } ${cellColor(wr, games)}`}
                          onMouseEnter={(e) =>
                            setHovered(games > 0 ? { key, x: e.clientX, y: e.clientY } : null)
                          }
                          onMouseLeave={() => setHovered(null)}
                        >
                          {games > 0 && (
                            <span className={`font-mono text-[10px] font-bold ${cellTextColor(wr, games)}`}>
                              {wr.toFixed(0)}%
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Tooltip flotante */}
          {hovered && cellMap.get(hovered.key) && (
            <div
              className="pointer-events-none fixed z-50 rounded-lg border border-gray-700 bg-[#1A1A24] px-3 py-2 shadow-xl"
              style={{
                left: Math.min(hovered.x + 14, window.innerWidth - 220),
                top: hovered.y - 14,
              }}
            >
              <p className="text-[11px] font-bold text-white">
                {formatTooltip(cellMap.get(hovered.key)!)}
              </p>
              <p className="mt-0.5 text-[10px] text-gray-400">
                {cellMap.get(hovered.key)!.games_played}{' '}
                {cellMap.get(hovered.key)!.games_played === 1 ? 'partida' : 'partidas'}
              </p>
            </div>
          )}

          {/* Legend */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-4 border-t border-gray-800 pt-3">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-600">Leyenda:</span>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-red-500/90" />
              <span className="text-[9px] text-gray-500">{"< 40%"}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-red-500/35" />
              <span className="text-[9px] text-gray-500">40-50%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm border border-gray-800 bg-[#0D0D12]" />
              <span className="text-[9px] text-gray-500">Sin datos</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-emerald-500/35" />
              <span className="text-[9px] text-gray-500">50-65%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3 w-3 rounded-sm bg-emerald-500/90" />
              <span className="text-[9px] text-gray-500">{"> 65%"}</span>
            </div>
          </div>
        </div>
      )}

      {/* Mejor / Peor horario (con umbral mínimo de 3 partidas) */}
      {!isLoading && !isError && cells.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {bestSlot ? (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                🏆 Mejor Horario
              </span>
              <p className="mt-1 text-sm font-bold text-white">
                {DAY_NAMES[bestSlot.day_of_week]} · {bestSlot.time_block}
              </p>
              <p className="text-xs text-gray-400">
                {bestSlot.winrate.toFixed(0)}% WR en {bestSlot.games_played} partidas (
                {bestSlot.wins}V - {bestSlot.losses}D)
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                🏆 Mejor Horario
              </span>
              <p className="mt-1 text-xs text-gray-400">
                Aún sin datos suficientes (mínimo 3 partidas por franja).
              </p>
            </div>
          )}
          {worstSlot ? (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-red-400">
                ⚠️ Peor Horario
              </span>
              <p className="mt-1 text-sm font-bold text-white">
                {DAY_NAMES[worstSlot.day_of_week]} · {worstSlot.time_block}
              </p>
              <p className="text-xs text-gray-400">
                {worstSlot.winrate.toFixed(0)}% WR en {worstSlot.games_played} partidas (
                {worstSlot.wins}V - {worstSlot.losses}D)
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                ⚠️ Peor Horario
              </span>
              <p className="mt-1 text-xs text-gray-400">
                Aún sin datos suficientes (mínimo 3 partidas por franja).
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}