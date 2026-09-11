import { useQuery } from '@tanstack/react-query'
import { getChampionRoleSummary } from '../api/client'

export function useChampionRoleSummary() {
  return useQuery({
    queryKey: ['champion-role-summary'],
    queryFn: getChampionRoleSummary,
    staleTime: 60_000,
  })
}
