import { useQuery } from '@tanstack/react-query'
import { getPatchAlert } from '../api/client'

export function usePatchAlert() {
  return useQuery({
    queryKey: ['patch-alert'],
    queryFn: getPatchAlert,
    // El parche cambia como mucho una vez por semana; revalidar en cada foco es ruido.
    staleTime: 60 * 60 * 1000,
    refetchOnWindowFocus: false,
  })
}