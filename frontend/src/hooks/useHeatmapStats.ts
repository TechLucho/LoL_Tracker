import { useQuery } from '@tanstack/react-query'
import { getHeatmapStats } from '../api/client'

export function useHeatmapStats() {
  return useQuery({
    queryKey: ['heatmap'],
    queryFn: getHeatmapStats,
    staleTime: 60_000,
  })
}
