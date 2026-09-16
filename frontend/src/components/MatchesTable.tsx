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

// ───────────── agrupación por sesiones (días) ─────────────
// Un remake no es una victoria/derrota real, así que se excluye del balance del día
// (mismo criterio que el backend: duración < 5 min). El día se deriva de la fecha
// local de la partida truncada a YYYY-MM-DD.

interface DayGroup {
  day: string
  wins: number
  losses: number
  matches: UIMatch[]
}

function isRemake(m: UIMatch): boolean {
  return m.game_duration_minutes != null && m.game_duration_minutes < 5
}

function localDayKey(dateStr: string): string {
  // "Logical Gaming Day": una sesión nocturna no se parte a medianoche. Restamos 4h
  // (4*60*60*1000 ms) antes de convertir a la fecha local, así una partida de las 03:00 AM
  // del 15 cae bajo el 14. Sólo afecta la cabecera del grupo, no el timestamp de la partida.
  const SESSION_OFFSET_MS = 4 * 60 * 60 * 1000
  return new Date(new Date(dateStr).getTime() - SESSION_OFFSET_MS).toLocaleDateString('sv-SE')
}

function groupByDay(matches: UIMatch[]): DayGroup[] {
  const groups = new Map<string, DayGroup>()
  for (const m of matches) {
    const day = localDayKey(m.date)
    let group = groups.get(day)
    if (!group) {
      group = { day, wins: 0, losses: 0, matches: [] }
      groups.set(day, group)
    }
    group.matches.push(m)
    if (!isRemake(m)) {
      if (m.win) group.wins += 1
      else group.losses += 1
    }
  }
  return [...groups.values()]
}

function formatDayLabel(day: string): string {
  const today = localDayKey(new Date().toISOString())
  const yesterday = localDayKey(new Date(Date.now() - 86_400_000).toISOString())
  if (day === today) return 'Hoy'
  if (day === yesterday) return 'Ayer'
  const d = new Date(`${day}T12:00:00`)
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
}

function SkeletonRow() {
  return (
    <div className={`${ROW_GRID} border-b border-hairline/50 px-4 py-3`}>
      <div className="flex items-center gap-1">
        <div className="shimmer h-10 w-10 rounded-lg bg-surface-2" />
        <div className="space-y-1">
          <div className="shimmer h-2 w-3 rounded bg-surface-2/60" />
          <div className="shimmer h-2 w-3 rounded bg-surface-2/60" />
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="shimmer h-3 w-16 rounded bg-surface-2" />
        <div className="shimmer h-2 w-28 rounded bg-surface-2/60" />
      </div>
      <div className="shimmer mx-auto h-4 w-16 rounded bg-surface-2" />
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-12 rounded bg-surface-2" />
        <div className="shimmer mx-auto h-2 w-10 rounded bg-surface-2/60" />
      </div>
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-8 rounded bg-surface-2" />
        <div className="shimmer mx-auto h-2 w-10 rounded bg-surface-2/60" />
      </div>
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-6 rounded bg-surface-2" />
        <div className="shimmer mx-auto h-2 w-6 rounded bg-surface-2/60" />
      </div>
      <div className="space-y-1">
        <div className="shimmer mx-auto h-3 w-8 rounded bg-surface-2" />
        <div className="shimmer mx-auto h-2 w-6 rounded bg-surface-2/60" />
      </div>
      <div>
        <div className="shimmer mx-auto h-6 w-10 rounded bg-surface-2" />
        <div className="shimmer mx-auto mt-1 h-1.5 w-8 rounded bg-surface-2/60" />
      </div>
      <div>
        <div className="shimmer mx-auto h-3 w-6 rounded bg-surface-2" />
        <div className="shimmer mx-auto mt-1 h-1.5 w-4 rounded bg-surface-2/60" />
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
    <div className="rounded-xl border border-hairline bg-surface-1">
      {/* Header with filter pills + sync button */}
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <div className="flex items-center gap-3">
          <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-accent-primary">
            ⚔️ Matches
          </h3>
          <div className="flex gap-1 rounded-lg bg-canvas p-0.5">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => onFilterChange(opt.key)}
                className={`rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
                  queueFilter === opt.key
                    ? 'bg-accent-primary text-white shadow-[0_0_24px_rgba(168,85,247,0.35)]'
                    : 'text-text-mute hover:text-text-body'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!isLoading && (
            <span className="text-xs text-text-mute">{matches.length} matches</span>
          )}
          <button
            onClick={onSync}
            disabled={isSyncing}
            className={`flex items-center gap-1.5 rounded-full px-5 py-2 text-xs font-bold uppercase tracking-wider transition-all active:scale-95 ${
              isSyncing
                ? 'cursor-not-allowed bg-surface-2 text-text-mute'
                : 'bg-accent-primary text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] hover:bg-accent-primary/90'
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
          <p className="mt-1 text-sm text-text-mute">Make sure the backend is running on localhost:8000</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && matches.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12">
          <Gamepad2 className="h-8 w-8 text-text-mute" />
          <p className="mt-3 text-base font-medium text-text-body">No matches found</p>
          <p className="mt-1 text-sm text-text-mute">
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
            {groupByDay(matches).map((group) => (
              <div key={group.day}>
                {/* Separador de sesión: fecha a la izquierda, balance a la derecha. */}
                <div className="flex items-center justify-between bg-surface-2 px-4 py-2.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-text-body">
                    {formatDayLabel(group.day)}
                  </span>
                  <span className="font-mono text-xs font-bold text-text-ink">
                    {group.wins}V - {group.losses}D
                  </span>
                </div>

                {group.matches.map((m) => {
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
                  className={`${ROW_GRID} cursor-pointer border-b border-hairline/50 px-4 py-3 transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary focus-visible:ring-inset ${
                    isExpanded ? 'bg-surface-2' : ''
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
                      className="h-10 w-10 rounded-lg border border-hairline"
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
                          className="h-[14px] w-[14px] rounded-sm border border-hairline"
                        />
                      )}
                      {spell2 && (
                        <img
                          src={spell2.url}
                          alt={spell2.name}
                          title={spell2.name}
                          className="h-[14px] w-[14px] rounded-sm border border-hairline"
                        />
                      )}
                    </div>
                  </div>

                  {/* Champion Info */}
                  <div className="min-w-0">
                    <span className="block truncate text-base font-bold text-white">{m.champion}</span>
                    <p className="truncate text-xs text-text-mute">
                      {m.role} · {m.duration_display} · {m.time_ago}
                      {queueLabel && <> · <span className="text-text-mute">{queueLabel}</span></>}
                    </p>
                  </div>

                  {/* Win/Loss Badge */}
                  <div className="text-center">
                    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-black uppercase tracking-wider ${
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
                    <p className={`font-mono text-xs font-bold ${
                      m.kda_ratio >= 5 ? 'text-emerald-400' : m.kda_ratio >= 3 ? 'text-text-body' : m.kda_ratio >= 2 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {m.kda_ratio.toFixed(2)} KDA
                    </p>
                  </div>

                  {/* CS */}
                  <div className="text-center">
                    <span className="font-mono text-base font-semibold text-white">{m.cs_total}</span>
                    <p className="text-xs text-text-mute">CS · {m.cs_min.toFixed(1)}/M</p>
                  </div>

                  {/* KP */}
                  <div className="text-center">
                    <span className="font-mono text-base font-semibold text-white">
                      {(m.kill_participation * 100).toFixed(0)}%
                    </span>
                    <p className="text-xs text-text-mute">KP</p>
                  </div>

                  {/* DPM */}
                  <div className="text-center">
                    <span className="font-mono text-base font-semibold text-white">{m.dpm}</span>
                    <p className="text-xs text-text-mute">DPM</p>
                  </div>

                  {/* Rating */}
                  <div className="text-center">
                    <span className={`font-mono text-2xl font-black leading-none ${
                      m.rating >= 80 ? 'text-orange-400' : m.rating >= 60 ? 'text-emerald-400' : m.rating >= 40 ? 'text-text-body' : 'text-red-400'
                    }`}>
                      {m.rating.toFixed(1)}
                    </span>
                    <p className="text-xs font-bold uppercase tracking-wider text-text-mute">Rating</p>
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
                        <p className="text-xs font-bold uppercase tracking-wider text-text-mute">LP</p>
                      </>
                    ) : (
                      <span className="text-text-mute">—</span>
                    )}
                  </div>
                </div>

                {/* Expanded Accordion */}
                {isExpanded && (
                  <div className="border-b border-hairline bg-canvas px-4 py-3">
                    <MatchAccordion match={m} onReviewSave={onReviewSave} isSaving={isSaving} />
                  </div>
                )}
                </div>
              )
            })}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Paginación: el historial ya no trunca en la primera página. Fuera del scroller
          horizontal para que siga centrado aunque la tabla esté desplazada. */}
      {!isLoading && !isError && hasMore && onLoadMore && (
        <div className="border-t border-hairline/50 px-4 py-3 text-center">
          <button
            onClick={onLoadMore}
            disabled={isLoadingMore}
            className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2.5 text-xs font-bold uppercase tracking-wider transition-all active:scale-95 ${
              isLoadingMore
                ? 'cursor-not-allowed bg-surface-2 text-text-mute'
                : 'bg-canvas text-accent-primary ring-1 ring-accent-primary/30 hover:bg-accent-primary/10'
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
