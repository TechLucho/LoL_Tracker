import { useMutation, useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import type { InfiniteData } from '@tanstack/react-query'
import { toast } from 'sonner'
import { isAxiosError } from 'axios'
import { getMatches, startSync, getSyncStatus, updateMatchReview } from '../api/client'
import type { BackendMatch, BackendParticipant, UIMatch, QueueFilter, MatchReviewUpdate } from '../data/types'

function computeKDA(kills: number, deaths: number, assists: number): number {
  if (deaths === 0) return kills + assists
  return +((kills + assists) / deaths).toFixed(2)
}

function formatDuration(minutes: number | null | undefined): string {
  if (!minutes) return '--:--'
  const m = Math.floor(minutes)
  const s = Math.round((minutes - m) * 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function timeAgo(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return '1d ago'
  return `${days}d ago`
}

function estimateDPM(kills: number, assists: number, csMin: number, duration: number): number {
  const base = (kills * 450 + assists * 250 + csMin * duration * 3.2)
  return Math.round(base / Math.max(duration, 1))
}

function computeDPMReal(totalDamage: number, duration: number): number {
  return Math.round(totalDamage / Math.max(duration, 1))
}

function estimateKP(kills: number, assists: number): number {
  const total = kills + assists
  if (total === 0) return 0
  return Math.min(1, (total / Math.max(total + 3, 1)))
}

function computeRating(win: boolean, kda: number, csMin: number, kp: number, deaths: number): number {
  let score = 50
  if (win) score += 15
  else score -= 15
  score += Math.min(20, (kda - 2) * 5)
  score += Math.min(10, (csMin - 7) * 3)
  score += Math.min(10, (kp - 0.5) * 20)
  score -= Math.min(15, Math.max(0, deaths - 3) * 5)
  return +Math.max(0, Math.min(100, score)).toFixed(1)
}

function findPlayerParticipant(
  participants: BackendParticipant[] | null | undefined,
  champion: string,
): BackendParticipant | undefined {
  if (!participants) return undefined
  // The main player is the one matching our champion name (case-insensitive)
  return participants.find(
    (p) => p.champion_name.toLowerCase() === champion.toLowerCase(),
  )
}

// Exportado para los tests unitarios de los fallbacks legacy.
export function mapBackendToUI(m: BackendMatch): UIMatch {
  const duration = m.game_duration_minutes ?? 25
  const me = findPlayerParticipant(m.participants, m.champion)

  // Use real spell IDs from participant data if available
  const spells: [number, number] = me
    ? [me.summoner_spells?.[0] ?? 4, me.summoner_spells?.[1] ?? 4]
    : [12, 4]

  // Use real damage numbers if available from participant data
  const dpm = me
    ? computeDPMReal(me.total_damage, duration)
    : estimateDPM(m.kills, m.assists, m.cs_min, duration)

  const kda_ratio = computeKDA(m.kills, m.deaths, m.assists)
  // El backend ya calcula KP y rating para los 10 participantes; sólo estimamos en local si la
  // fila es de una sincronización anterior al nuevo esquema (sin esos campos).
  const kill_participation = me?.kill_participation ?? estimateKP(m.kills, m.assists)
  const rating = me?.rating ?? computeRating(m.win, kda_ratio, m.cs_min, kill_participation, m.deaths)

  return {
    game_id: m.game_id,
    date: m.date,
    champion: m.champion,
    role: m.role,
    kills: m.kills,
    deaths: m.deaths,
    assists: m.assists,
    cs_total: m.cs_total,
    cs_min: m.cs_min,
    control_wards: m.control_wards,
    win: m.win,
    enemy_champion: m.enemy_champion ?? 'Unknown',
    game_duration_minutes: duration,
    duration_display: formatDuration(m.game_duration_minutes),
    time_ago: timeAgo(m.date),
    spells,
    kda_ratio,
    kill_participation,
    dpm,
    rating,
    queue_id: m.queue_id ?? null,
    participants: m.participants?.map((p) => ({
      champion_name: p.champion_name,
      puuid: p.puuid,
      player_name: p.player_name,
      kills: p.kills,
      deaths: p.deaths,
      assists: p.assists,
      cs: p.cs,
      items: p.items ?? [],
      summoner_spells: p.summoner_spells ?? [],
      team_id: p.team_id,
      team_position: p.team_position,
      win: p.win,
      total_damage: p.total_damage,
      total_damage_taken: p.total_damage_taken,
      gold_earned: p.gold_earned,
      vision_score: p.vision_score,
      kill_participation: p.kill_participation,
      rating: p.rating,
    })) ?? null,
    lp_change: m.lp_change ?? null,
    tilt_level: m.tilt_level ?? null,
    impact_rating: m.impact_rating ?? null,
    notes: m.notes ?? null,
    vod_review: m.vod_review ?? null,
  }
}

// Tamaño de página del backend (limit/offset). 50 partidas por carga: el primer render trae
// el historial reciente y "Cargar más" pagina el resto sin truncar silenciosamente.
export const MATCHES_PAGE_SIZE = 50

export function useMatches(queueFilter: QueueFilter) {
  return useInfiniteQuery({
    queryKey: ['matches', queueFilter],
    queryFn: async ({ pageParam }) => {
      const raw = await getMatches(queueFilter, MATCHES_PAGE_SIZE, pageParam)
      return raw.map(mapBackendToUI)
    },
    initialPageParam: 0,
    // Mientras el backend devuelva páginas llenas puede haber más; una corta es el final.
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === MATCHES_PAGE_SIZE ? allPages.length * MATCHES_PAGE_SIZE : undefined,
    staleTime: 30_000,
  })
}

const SYNC_POLL_INTERVAL_MS = 2_500
// Tope de seguridad: si el backend sigue en 'processing' tras 10 min, soltamos y avisamos.
const SYNC_MAX_WAIT_MS = 10 * 60_000

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function useSyncMatches(options: { silent?: boolean } = {}) {
  const queryClient = useQueryClient()
  // Modo silencioso (auto-sync al abrir la app): sin toasts de "todo actualizado" ni errores
  // (el HealthBanner ya comunica si el backend está caído o la key expiró). Sólo se habla
  // cuando hay partidas nuevas que celebrar; las invalidaciones refrescan la UI igualmente.
  const silent = options.silent ?? false
  return useMutation({
    mutationFn: async () => {
      // El POST responde 202 al instante; el spinner vive mientras dure el polling.
      await startSync()
      const deadline = Date.now() + SYNC_MAX_WAIT_MS
      while (Date.now() < deadline) {
        await sleep(SYNC_POLL_INTERVAL_MS)
        const status = await getSyncStatus()
        if (status.status === 'success') return status.result
        if (status.status === 'error') throw new Error(status.error ?? 'El sync falló en el backend')
        if (status.status === 'idle') return null // el backend se reinició mientras sondeábamos
      }
      throw new Error('El sync tardó demasiado. Revisa /api/sync/status.')
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      if (silent) {
        if (result && result.inserted > 0) {
          toast.success(`✅ ${result.inserted} partidas nuevas sincronizadas`)
        }
        return
      }
      if (result && result.errors.length > 0) {
        toast.warning(`⚠️ Sync con fallos: ${result.inserted} nuevas, ${result.errors.length} partidas no descargadas`)
      } else if (result && result.inserted > 0) {
        toast.success(`✅ ${result.inserted} partidas nuevas sincronizadas`)
      } else {
        toast.success('✅ Todo actualizado, sin partidas nuevas')
      }
    },
    onError: (err) => {
      if (silent) return
      const detail = isAxiosError(err)
        ? (err.response?.data as { detail?: string } | undefined)?.detail
        : undefined
      toast.error(detail ? `❌ ${detail}` : `❌ ${err.message || 'Error al sincronizar con Riot'}`)
    },
  })
}

export function useUpdateMatchReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ gameId, data }: { gameId: string; data: MatchReviewUpdate }) =>
      updateMatchReview(gameId, data),
    // Optimistic update (audit 2026-08-24): la UI pinta la review al instante; si el PATCH
    // falla, el snapshot se restaura sin parpadeos y sólo entonces se habla (toast de error).
    onMutate: async ({ gameId, data }) => {
      // Congelar refetches en vuelo: un 'matches' fresco del servidor pisaría el estado optimista.
      await queryClient.cancelQueries({ queryKey: ['matches'] })
      // Snapshot de TODAS las cachés de matches (una por filtro de cola, cada una con páginas).
      const previous = queryClient.getQueriesData<InfiniteData<UIMatch[]>>({
        queryKey: ['matches'],
      })
      for (const [key, cache] of previous) {
        if (!cache) continue
        queryClient.setQueryData<InfiniteData<UIMatch[]>>(key, {
          ...cache,
          pages: cache.pages.map((page) =>
            page.map((m) => (m.game_id === gameId ? { ...m, ...data } : m)),
          ),
        })
      }
      return { previous }
    },
    onSuccess: () => {
      toast.success('✅ Review guardada')
    },
    onError: (_error, _vars, context) => {
      context?.previous.forEach(([key, snapshot]) => {
        if (snapshot) queryClient.setQueryData(key, snapshot)
      })
      toast.error('❌ No se pudo guardar la review. ¿Está el backend corriendo?')
    },
    onSettled: () => {
      // Con éxito o tras rollback, siempre resincronizar con la verdad del servidor.
      queryClient.invalidateQueries({ queryKey: ['matches'] })
    },
  })
}
