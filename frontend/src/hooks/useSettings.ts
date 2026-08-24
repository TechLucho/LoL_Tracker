import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSettings, updateSettings } from '../api/client'
import type { UserSettingsUpdate } from '../data/types'

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
