import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import FormCheckCard from '../components/FormCheckCard'
import PerformanceNotes from '../components/PerformanceNotes'
import RecordsCard from '../components/RecordsCard'
import ChampionsList from '../components/ChampionsList'
import RatingTrend from '../components/RatingTrend'
import MatchesTable from '../components/MatchesTable'
import { useMatches, useSyncMatches, useUpdateMatchReview } from '../hooks/useMatches'
import { useChampionStats } from '../hooks/useChampionStats'
import type { QueueFilter } from '../data/types'

const QUEUE_FILTER_KEY = 'lol_tracker.queue_filter'
const VALID_FILTERS: QueueFilter[] = ['all', 'ranked', 'normal']

function loadStoredFilter(): QueueFilter {
  try {
    const stored = localStorage.getItem(QUEUE_FILTER_KEY)
    if (stored && VALID_FILTERS.includes(stored as QueueFilter)) return stored as QueueFilter
  } catch {
    // localStorage puede fallar en modo privado: filtro por defecto y listo
  }
  return 'all'
}

function isQueueFilter(value: string | null): value is QueueFilter {
  return value !== null && VALID_FILTERS.includes(value as QueueFilter)
}

export default function Dashboard() {
  // Deep-linking (auditoría): el filtro vive en la URL (`#/?queue=ranked`) y localStorage.
  // La URL MANDA si existe un valor válido; localStorage sólo es el fallback al entrar sin
  // parámetro, así que compartir un link preserva exactamente la vista del que lo envió.
  const [searchParams, setSearchParams] = useSearchParams()
  const storedFilter = useMemo(loadStoredFilter, [])
  const urlQueue = searchParams.get('queue')
  const queueFilter: QueueFilter = isQueueFilter(urlQueue) ? urlQueue : storedFilter

  const {
    data,
    isLoading,
    isError,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useMatches(queueFilter)
  // Las páginas del infinite query se aplanan una sola vez por cambio de datos; de la lista
  // resultante se alimentan también FormCheck, Performance Notes y Records.
  const matches = useMemo(() => data?.pages.flat() ?? [], [data])
  const { data: championStats = [], isLoading: championsLoading } = useChampionStats()
  const syncMutation = useSyncMatches()
  const reviewMutation = useUpdateMatchReview()

  const handleSync = () => {
    syncMutation.mutate()
  }

  const handleFilterChange = (f: QueueFilter) => {
    const next = new URLSearchParams(searchParams)
    next.set('queue', f)
    // replace: cambiar de filtro no es navegación, no debe apilar entradas en el historial
    setSearchParams(next, { replace: true })
    try {
      localStorage.setItem(QUEUE_FILTER_KEY, f)
    } catch {
      // sin persistencia disponible, el filtro vive sólo en la URL/memoria
    }
  }

  const handleReviewSave = (gameId: string, data: import('../data/types').MatchReviewUpdate) => {
    reviewMutation.mutate({ gameId, data })
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_280px] 2xl:grid-cols-[1fr_320px]">
        {/* Main Column */}
        <div className="space-y-3">
          <FormCheckCard matches={matches} />

          <PerformanceNotes matches={matches} />

          <MatchesTable
            matches={matches}
            isLoading={isLoading}
            isError={isError}
            queueFilter={queueFilter}
            onFilterChange={handleFilterChange}
            onSync={handleSync}
            isSyncing={syncMutation.isPending}
            onReviewSave={handleReviewSave}
            isSaving={reviewMutation.isPending}
            hasMore={hasNextPage ?? false}
            onLoadMore={() => fetchNextPage()}
            isLoadingMore={isFetchingNextPage}
          />
        </div>

        {/* Right Sidebar */}
        <div className="space-y-3">
          <RecordsCard matches={matches} />
          <RatingTrend />
          <ChampionsList champions={championStats} isLoading={championsLoading} />
        </div>
      </div>
    </div>
  )
}
