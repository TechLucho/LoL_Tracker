import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  getChampionIndex,
  getItemIndex,
  getSpellIndex,
} from '../api/client'
import type { ChampionMeta } from '../api/client'
import { DDragon, SUMMONER_SPELLS } from '../data/constants'

// El parche cambia como mucho cada dos semanas; 1h de frescura evita martillear al backend
// en cada montaje de componente (React Query deduplica las tres queries entre vistas).
const METADATA_STALE_MS = 60 * 60 * 1000

export function useChampionIndex() {
  return useQuery({
    queryKey: ['metadata', 'champions'],
    queryFn: getChampionIndex,
    staleTime: METADATA_STALE_MS,
    retry: 1,
  })
}

export function useItemIndex() {
  return useQuery({
    queryKey: ['metadata', 'items'],
    queryFn: getItemIndex,
    staleTime: METADATA_STALE_MS,
    retry: 1,
  })
}

export function useSpellIndex() {
  return useQuery({
    queryKey: ['metadata', 'spells'],
    queryFn: getSpellIndex,
    staleTime: METADATA_STALE_MS,
    retry: 1,
  })
}

export interface IconInfo {
  url: string
  /** Nombre real para el tooltip; '' = aún sin metadatos (no se muestra tooltip). */
  name?: string
}

/**
 * Resolvedores de iconos centralizados en el backend. Mientras los metadatos cargan (o si el
 * endpoint falla) se cae a las constantes locales de constants.ts: la UI nunca se queda sin
 * imagen, sólo pierde el tooltip hasta que llegan.
 */
export function useIcons() {
  const { data: champIndex } = useChampionIndex()
  const { data: itemIndex } = useItemIndex()
  const { data: spellIndex } = useSpellIndex()

  return useMemo(() => {
    // Índice nombre-visible -> metadato. Mata el mapa de excepciones del frontend:
    // "Lee Sin", "Nunu & Willump" o "Dr. Mundo" resuelven directo contra Data Dragon.
    const byName = new Map<string, ChampionMeta>()
    for (const c of Object.values(champIndex?.champions ?? {})) {
      byName.set(c.name.toLowerCase(), c)
    }

    return {
      champion(displayName: string): IconInfo {
        const meta = byName.get(displayName.toLowerCase())
        if (meta) {
          const label = meta.title ? `${meta.name} — ${meta.title}` : meta.name
          return { url: meta.image, name: label }
        }
        return { url: DDragon.champion(displayName), name: displayName }
      },
      item(id: number): IconInfo | null {
        if (!id || id <= 0) return null
        const meta = itemIndex?.items[String(id)]
        if (meta) return { url: meta.image, name: meta.name }
        return { url: DDragon.item(id) }
      },
      spell(id: number): IconInfo | null {
        const meta = spellIndex?.spells[String(id)]
        if (meta) return { url: meta.image, name: meta.name }
        const legacy = SUMMONER_SPELLS[id]
        return legacy ? { url: legacy.icon, name: legacy.name } : null
      },
    }
  }, [champIndex, itemIndex, spellIndex])
}

/** Lista completa de campeones ordenada por nombre visible — para el buscador de Settings. */
export function useChampionList(): ChampionMeta[] {
  const { data } = useChampionIndex()
  return useMemo(
    () =>
      Object.values(data?.champions ?? {}).sort((a, b) =>
        a.name.localeCompare(b.name),
      ),
    [data],
  )
}
