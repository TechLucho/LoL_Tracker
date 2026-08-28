import { useQuery } from '@tanstack/react-query'
import { getKpiTrends } from '../api/client'

export function useKpiTrends(limit = 50) {
  return useQuery({
    queryKey: ['kpi-trends', limit],
    queryFn: () => getKpiTrends(limit),
    staleTime: 60_000,
  })
}
