import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSettings, updateSettings, linkRiot } from '../api/client'
import type { UserSettingsUpdate, RiotLinkRequest } from '../data/types'

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 60_000,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: UserSettingsUpdate) => updateSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['settings'], data)
    },
  })
}

export function useLinkRiot() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: RiotLinkRequest) => linkRiot(payload),
    onSuccess: (data) => {
      // Cambio inmediato para que el gate desmonte el onboarding sin esperar red; un refetch
      // detrás rellena los canónicos (regions, impact_ratings) que el PUT no devuelve.
      queryClient.setQueryData(['settings'], data)
      void queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}
