import { useQuery } from '@tanstack/react-query'
import { getChampionStats } from '../api/client'

export function useChampionStats() {
  return useQuery({
    queryKey: ['champion-stats'],
    queryFn: getChampionStats,
    staleTime: 60_000,
  })
}
