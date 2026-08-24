import { useQuery } from '@tanstack/react-query'
import { getConstitutionStatus } from '../api/client'

export function useConstitution() {
  return useQuery({
    queryKey: ['constitution'],
    queryFn: getConstitutionStatus,
    staleTime: 30_000,
  })
}
