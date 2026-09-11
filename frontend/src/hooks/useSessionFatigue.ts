import { useQuery } from '@tanstack/react-query'
import { getSessionFatigue } from '../api/client'

export function useSessionFatigue() {
  return useQuery({
    queryKey: ['session-fatigue'],
    queryFn: getSessionFatigue,
    staleTime: 60_000,
  })
}
