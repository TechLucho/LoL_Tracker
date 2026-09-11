import { useQuery } from '@tanstack/react-query'
import { getScoutOpponent } from '../api/client'

/**
 * Escout del rival de una partida.
 *
 * `enabled` lo controla el tab activo del accordion: no se dispara para los 50 matches de la
 * tabla, sólo cuando el usuario abre con intención el tab de Escout (ahorra una llamada a Riot).
 */
export function useScoutOpponent(gameId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['scout-opponent', gameId],
    queryFn: () => getScoutOpponent(gameId),
    enabled,
    // El backend cachea 24h; staleTime largo evita re-validar en cada apertura del tab.
    staleTime: 24 * 60 * 60 * 1000,
    retry: 1,
  })
}