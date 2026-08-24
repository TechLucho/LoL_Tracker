import { useQuery } from '@tanstack/react-query'
import { getHealthStatus } from '../api/client'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealthStatus,
    staleTime: 30_000,
    // Si el backend está caído no insistas en cada render: un reintento y basta.
    retry: 1,
    // Sondeo en vivo: si el backend se cae, el banner naranja aparece; cuando vuelve,
    // este refetch lo quita sin recargar la página.
    refetchInterval: 60_000,
  })
}
