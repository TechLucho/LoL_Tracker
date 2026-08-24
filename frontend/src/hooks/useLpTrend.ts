import { useQuery } from '@tanstack/react-query'
import { getLpTrend } from '../api/client'

// La gráfica es de LP acumulado: sólo Solo/Duo (420) tiene LP. Las normales/flex entrarían
// como 0 y aplastarían la curva — el backend soporta ?queue= para acotar.
const RANKED_SOLO_QUEUE_ID = 420

export function useLpTrend(limit = 30) {
  return useQuery({
    queryKey: ['lp-trend', limit],
    queryFn: () => getLpTrend(limit, RANKED_SOLO_QUEUE_ID),
    staleTime: 30_000,
  })
}
