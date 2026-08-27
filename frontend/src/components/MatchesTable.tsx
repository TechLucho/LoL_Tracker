import { useState } from 'react'
import { ChevronDown, RefreshCw, Gamepad2 } from 'lucide-react'
import type { UIMatch, QueueFilter, MatchReviewUpdate } from '../data/types'
import { DDragon, QUEUE_LABELS } from '../data/constants'
import { useIcons } from '../hooks/useMetadata'
import MatchAccordion from './MatchAccordion'

const FILTER_OPTIONS: { key: QueueFilter; label: string }[] = [
  { key: 'all', label: 'All Matches' },
  { key: 'ranked', label: 'Ranked' },
  { key: 'normal', label: 'Normal' },
]

// Grid de la fila: [avatar+spells] [info] [badge] [KDA] [CS] [KP] [DPM] [Rating] [LP].
// Columnas fijas para las métricas -> quedan alineadas en vertical entre filas pase lo que
// pase con el texto; sólo la columna de información es flexible.
const ROW_GRID =
  'grid grid-cols-[auto_minmax(130px,1fr)_84px_88px_68px_56px_64px_72px_52px] items-center gap-x-3'

function SkeletonRow() {
  return (
    <div className={`${ROW_GRID} border-b border-gray-800/50 px-4 py-3`}>
      <div className="flex items-center gap-1">
        <div className="shimmer h-10 w-10 rounded-lg bg-gray-800" />
        <div className="space-y-1">
          <div className="shimmer h-2 w-3 rounded bg-gray-800/60" />
          <div className="shimmer h-2 w-3 rounded bg-gray-800/60" />
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="shimmer h-3 w-16 rounded bg-gray-800" />
        <div className="shimmer h-2 w-28 rounded bg-gray-800/60" />
      </div>
      <div className="shimmer mx-auto h-4 w-16 rounded bg-gray-800" />
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-12 rounded bg-gray-800" />
        <div className="shimmer mx-auto h-2 w-10 rounded bg-gray-800/60" />
      </div>
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-8 rounded bg-gray-800" />
        <div className="shimmer mx-auto h-2 w-10 rounded bg-gray-800/60" />
      </div>
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-6 rounded bg-gray-800" />
        <div className="shimmer mx-auto h-2 w-6 rounded bg-gray-800/60" />
      </div>
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-8 rounded bg-gray-800" />
        <div className="shimmer mx-auto h-2 w-6 rounded bg-gray-800/60" />
      </div>
      <div>
        <div className="shimmer mx-auto h-6 w-10 rounded bg-gray-800" />
        <div className="shimmer mx-auto mt-1 h-1.5 w-8 rounded bg-gray-800/60" />
      </div>
      <div>
        <div className="shimmer mx-auto h-3 w-6 rounded bg-gray-800" />
        <div className="shimmer mx-auto mt-1 h-1.5 w-4 rounded bg-gray-800/60" />
      </div>
    </div>
  )
}

interface Props {
  matches: UIMatch[]
  isLoading: boolean
  isError: boolean
  queueFilter: QueueFilter
  onFilterChange: (f: QueueFilter) => void
  onSync: () => void
  isSyncing: boolean
  onReviewSave: (gameId: string, data: MatchReviewUpdate) => void
  isSaving: boolean
  hasMore?: boolean
  onLoadMore?: () => void
  isLoadingMore?: boolean
}

export default function MatchesTable({ matches, isLoading, isError, queueFilter, onFilterChange, onSync, isSyncing, onReviewSave, isSaving, hasMore = false, onLoadMore, isLoadingMore = false }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const icons = useIcons()

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C]">
      {/* Header with filter pills + sync button */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-bold uppercase tracking-widest text-purple-400">
            ⚔️ Matches
          </h3>
          <div className="flex gap-1 rounded-lg bg-[#0A0A10] p-0.5">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => onFilterChange(opt.key)}
                className={`rounded-md px-3 py-2 text-[11px] font-semibold transition-colors ${
                  queueFilter === opt.key
                    ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/20'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!isLoading && (
            <span className="text-[11px] text-gray-500">{matches.length} matches</span>
          )}
          <button
            onClick={onSync}
            disabled={isSyncing}
            className={`flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[11px] font-bold uppercase tracking-wider transition-all active:scale-95 ${
              isSyncing
                ? 'cursor-not-allowed bg-gray-800 text-gray-500'
                : 'bg-purple-500 text-white shadow-lg shadow-purple-500/20 hover:bg-purple-400'
            }`}
          >
            <RefreshCw className={`h-3 w-3 ${isSyncing ? 'animate-spin' : ''}`} />
            {isSyncing ? 'Syncing...' : 'Sync'}
          </button>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="overflow-x-auto">
          <div className="flex flex-col">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-12">
          <span className="text-lg">⚠️</span>
          <p className="mt-2 text-base font-medium text-red-400">Failed to load matches</p>
          <p className="mt-1 text-sm text-gray-500">Make sure the backend is running on localhost:8000</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && matches.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12">
          <Gamepad2 className="h-8 w-8 text-gray-600" />
          <p className="mt-3 text-base font-medium text-gray-300">No matches found</p>
          <p className="mt-1 text-sm text-gray-500">
            {queueFilter !== 'all'
              ? `No ${queueFilter} matches yet. Try "All Matches".`
              : 'Click "Sync" to download your latest matches from Riot.'}
          </p>
        </div>
      )}

      {/* Match rows. El grid de fila suma ~710px de columnas fijas: en <768px el wrapper
          permite scroll horizontal en vez de aplastar las columnas (audit 2026-08-24). */}
      {!isLoading && !isError && matches.length > 0 && (
        <div className="overflow-x-auto">
          <div className="flex flex-col">
            {matches.map((m) => {
            const isExpanded = expandedId === m.game_id
            const champIcon = icons.champion(m.champion)
            const spell1 = icons.spell(m.spells[0])
            const spell2 = icons.spell(m.spells[1])
            const queueLabel = m.queue_id != null ? QUEUE_LABELS[m.queue_id] : null
            return (
              <div key={m.game_id}>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setExpandedId(isExpanded ? null : m.game_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setExpandedId(isExpanded ? null : m.game_id)
                    }
                  }}
                  className={`${ROW_GRID} cursor-pointer border-b border-gray-800/50 px-4 py-3 transition-colors hover:bg-white/[0.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-inset ${
                    isExpanded ? 'bg-white/[0.03]' : ''
                  } bg-gradient-to-r ${
                    m.win
                      ? 'from-emerald-500/[0.09] via-emerald-500/[0.03] to-transparent'
                      : 'from-red-500/[0.09] via-red-500/[0.03] to-transparent'
                  }`}
                >
                  {/* Champion Avatar + Spells */}
                  <div className="flex items-center gap-1">
                    <img
                      src={champIcon.url}
                      alt={m.champion}
                      title={champIcon.name}
                      className="h-10 w-10 rounded-lg border border-gray-700"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                      }}
                    />
                    <div className="flex flex-col gap-0.5">
                      {spell1 && (
                        <img
                          src={spell1.url}
                          alt={spell1.name}
                          title={spell1.name}
                          className="h-[14px] w-[14px] rounded-sm border border-gray-700"
                        />
                      )}
                      {spell2 && (
                        <img
                          src={spell2.url}
                          alt={spell2.name}
                          title={spell2.name}
                          className="h-[14px] w-[14px] rounded-sm border border-gray-700"
                        />
                      )}
                    </div>
                  </div>

                  {/* Champion Info */}
                  <div className="min-w-0">
                    <span className="block truncate text-base font-bold text-white">{m.champion}</span>
                    <p className="truncate text-[11px] text-gray-500">
                      {m.role} · {m.duration_display} · {m.time_ago}
                      {queueLabel && <> · <span className="text-gray-600">{queueLabel}</span></>}
                    </p>
                  </div>

                  {/* Win/Loss Badge */}
                  <div className="text-center">
                    <span className={`inline-block rounded px-2 py-0.5 text-[11px] font-black uppercase tracking-wider ${
                      m.win
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : 'bg-red-500/20 text-red-400'
                    }`}>
                      {m.win ? 'VICTORY' : 'DEFEAT'}
                    </span>
                  </div>

                  {/* KDA */}
                  <div className="text-center">
                    <span className="font-mono text-base font-bold text-white">
                      {m.kills}/{m.deaths}/{m.assists}
                    </span>
                    <p className={`font-mono text-[11px] font-bold ${
                      m.kda_ratio >= 5 ? 'text-emerald-400' : m.kda_ratio >= 3 ? 'text-gray-300' : m.kda_ratio >= 2 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {m.kda_ratio.toFixed(2)} KDA
                    </p>
                  </div>

                  {/* CS */}
                  <div className="text-center">
                    <span className="font-mono text-base font-semibold text-white">{m.cs_total}</span>
                    <p className="text-[11px] text-gray-500">CS · {m.cs_min.toFixed(1)}/M</p>
                  </div>

                  {/* KP */}
                  <div className="text-center">
                    <span className="font-mono text-base font-semibold text-white">
                      {(m.kill_participation * 100).toFixed(0)}%
                    </span>
                    <p className="text-[11px] text-gray-500">KP</p>
                  </div>

                  {/* DPM */}
                  <div className="text-center">
                    <span className="font-mono text-base font-semibold text-white">{m.dpm}</span>
                    <p className="text-[11px] text-gray-500">DPM</p>
                  </div>

                  {/* Rating */}
                  <div className="text-center">
                    <span className={`font-mono text-2xl font-black leading-none ${
                      m.rating >= 80 ? 'text-orange-400' : m.rating >= 60 ? 'text-emerald-400' : m.rating >= 40 ? 'text-gray-300' : 'text-red-400'
                    }`}>
                      {m.rating.toFixed(1)}
                    </span>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-gray-600">Rating</p>
                  </div>

                  {/* LP */}
                  <div className="text-center">
                    {m.lp_change !== null ? (
                      <>
                        <span className={`font-mono text-base font-bold ${
                          m.lp_change > 0 ? 'text-emerald-400' : 'text-red-400'
                        }`}>
                          {m.lp_change > 0 ? '+' : ''}{m.lp_change}
                        </span>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-600">LP</p>
                      </>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </div>
                </div>

                {/* Expanded Accordion */}
                {isExpanded && (
                  <div className="border-b border-gray-800 bg-[#0D0D12] px-4 py-3">
                    <MatchAccordion match={m} onReviewSave={onReviewSave} isSaving={isSaving} />
                  </div>
                )}
              </div>
            )
          })}

          </div>
        </div>
      )}

      {/* Paginación: el historial ya no trunca en la primera página. Fuera del scroller
          horizontal para que siga centrado aunque la tabla esté desplazada. */}
      {!isLoading && !isError && hasMore && onLoadMore && (
        <div className="border-t border-gray-800/50 px-4 py-3 text-center">
          <button
            onClick={onLoadMore}
            disabled={isLoadingMore}
            className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider transition-all active:scale-95 ${
              isLoadingMore
                ? 'cursor-not-allowed bg-gray-800 text-gray-500'
                : 'bg-[#0A0A10] text-purple-300 ring-1 ring-purple-500/30 hover:bg-purple-500/10'
            }`}
          >
            <ChevronDown className={`h-3.5 w-3.5 ${isLoadingMore ? 'animate-bounce' : ''}`} />
            {isLoadingMore ? 'Cargando...' : `Cargar más (mostrando ${matches.length})`}
          </button>
        </div>
      )}
    </div>
  )
}
