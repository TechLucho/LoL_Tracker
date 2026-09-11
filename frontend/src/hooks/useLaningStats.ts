import { useQuery } from '@tanstack/react-query'
import { getLaningStats } from '../api/client'

export function useLaningStats(limit = 50) {
  return useQuery({
    queryKey: ['laning', limit],
    queryFn: () => getLaningStats(limit),
    // Los promedios cambian sólo al sincronizar partidas nuevas; revalidar cada foco es ruido.
    staleTime: 60_000,
  })
}