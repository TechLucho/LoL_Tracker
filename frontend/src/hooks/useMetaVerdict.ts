import { useQuery } from '@tanstack/react-query'
import { getMetaVerdict } from '../api/client'

export function useMetaVerdict() {
  return useQuery({
    queryKey: ['meta-verdict'],
    queryFn: getMetaVerdict,
    staleTime: 60_000,
  })
}