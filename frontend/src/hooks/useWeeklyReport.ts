import { useQuery } from '@tanstack/react-query'
import { getWeeklyReport } from '../api/client'

export function useWeeklyReport() {
  return useQuery({
    queryKey: ['weekly-report'],
    queryFn: getWeeklyReport,
    staleTime: 60_000,
  })
}
