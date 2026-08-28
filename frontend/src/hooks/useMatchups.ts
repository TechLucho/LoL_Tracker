import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  getMatchupStats,
  getMatchupNotes,
  updateMatchupNotes,
} from '../api/client'
import type { MatchupNotesUpdate } from '../api/client'

const matchupKey = (user: string, enemy: string) =>
  ['matchups', user.toLowerCase(), enemy.toLowerCase()] as const

/** Estadísticas históricas del cruce. Si la pareja no se seleccionó aún, deshabilitada. */
export function useMatchupStats(userChampion: string | null, enemyChampion: string | null) {
  const enabled = Boolean(userChampion && enemyChampion)
  return useQuery({
    queryKey: ['matchup-stats', userChampion ?? '', enemyChampion ?? ''],
    queryFn: () => getMatchupStats(userChampion!, enemyChampion!),
    enabled,
    staleTime: 60_000,
  })
}

/** Bloc de notas del cruce. Activo sólo con ambos campeones elegidos. */
export function useMatchupNotes(userChampion: string | null, enemyChampion: string | null) {
  const enabled = Boolean(userChampion && enemyChampion)
  return useQuery({
    queryKey: matchupKey(userChampion ?? '', enemyChampion ?? ''),
    queryFn: () => getMatchupNotes(userChampion!, enemyChampion!),
    enabled,
    staleTime: 60_000,
  })
}

export function useUpdateMatchupNotes(userChampion: string, enemyChampion: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (notes: string) => {
      const payload: MatchupNotesUpdate = { notes }
      return updateMatchupNotes(userChampion, enemyChampion, payload)
    },
    onSuccess: (data) => {
      // Refresca la caché local con lo que devolvió el servidor (incluye updated_at).
      queryClient.setQueryData(matchupKey(userChampion, enemyChampion), data)
      toast.success('✅ Notas guardadas')
    },
    onError: () => {
      toast.error('❌ No se pudieron guardar las notas. ¿Está el backend corriendo?')
    },
  })
}
