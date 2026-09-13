import axios from 'axios'
import { toast } from 'sonner'
import { supabase } from '../lib/supabase'
import { queryClient } from '../lib/queryClient'
import type { MatchReviewUpdate } from '../data/types'
import type {
  BackendMatch,
  HealthStatus,
  ChampionsIndex,
  ItemsIndex,
  SpellsIndex,
  UserSettings,
  UserSettingsUpdate,
  ChampionStats,
  ChampionRoleSummary,
  HeatmapResponse,
  LaningSummary,
  PatchAlert,
  SyncStatus,
  SyncAccepted,
  MatchupStats,
  MatchupNotes,
  MatchupNotesUpdate,
  TrendPoint,
  WeeklyReport,
  SessionFatigue,
  ScoutOpponent,
  MetaVerdictResponse,
  RiotLinkRequest,
} from './generated'
// Re-export generated types that are used by other modules.
export type {
  BackendMatch,
  HealthStatus,
  ChampionStats,
  ChampionRoleSummary,
  HeatmapCell,
  HeatmapResponse,
  PatchAlert,
  PatchChampionInfo,
  LaningSummary,
  ChampionMeta,
  MatchupStats,
  MatchupNotes,
  MatchupNotesUpdate,
  TrendPoint,
  WeeklyReport,
  SessionFatigue,
  ScoutMasteryChampion,
  ScoutOpponent,
  MetaVerdict,
  MetaVerdictResponse,
} from './generated'
// Producción: la URL deja de estar hardcodeada (VITE_API_URL en el build del hosting) y cae
// al origen de desarrollo local si no está definida.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
})

// Auth: cada petición lleva el token de sesión de Supabase. Se obtiene la sesión en cada
// llamada a propósito (no al arrancar): así el interceptor se entera al instante de logins y
// logout sin reiniciar la SPA.
api.interceptors.request.use(async (config) => {
  try {
    const { data } = await supabase.auth.getSession()
    if (data.session?.access_token) {
      config.headers.set('Authorization', `Bearer ${data.session.access_token}`)
    }
  } catch {
    // Sin Supabase configurado la sesión es nula: la petición sale sin token y el backend
    // responde 401 — nunca rompe el interceptor.
  }
  return config
})

// ───────────────────────── 401 global: sesión caducada/revocada ─────────────────────────
// Al detectar un 401 (token expirado, revocado o sin sesión) se cierra la sesión de Supabase,
// se vacía la caché de TanStack Query (nada de datos del usuario anterior en el caché) y se
// avisa. El redirect NO vive aquí: `supabase.auth.signOut()` dispara `onAuthStateChange` y el
// AuthProvider pone la sesión a null, con lo que RequireAuth redirige a /login conservando la
// ruta previa en `state.from`. Los 401 simultáneos (varias queries en vuelo) se colapsan en uno.

let handlingUnauthorized = false

function handleUnauthorized(): void {
  if (handlingUnauthorized) return
  handlingUnauthorized = true
  queryClient.clear()
  toast.error('🕐 Sesión expirada. Vuelve a iniciar sesión.')
  // `scope: 'local'` a propósito: un revoke en servidor (scope global) hace red y puede fallar
  // dejando al usuario atrapado en un bucle de 401. Aquí el token ya es inválido — sólo hay
  // que limpiar la sesión local; el onAuthStateChange del provider tira del logout.
  void supabase.auth.signOut({ scope: 'local' }).catch(() => {})
}

// El guard se rearma con cada login: si la nueva sesión vuelve a caducar, el aviso se repite.
supabase.auth.onAuthStateChange((event) => {
  if (event === 'SIGNED_IN') handlingUnauthorized = false
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      handleUnauthorized()
    }
    return Promise.reject(error)
  },
)

export async function getMatches(queueType: string, limit = 50, offset = 0): Promise<BackendMatch[]> {
  const params: Record<string, string | number> = { limit, offset }
  if (queueType !== 'all') {
    params.queue = queueType
  }
  const { data } = await api.get<BackendMatch[]>('/matches', { params })
  return data
}

export async function startSync(): Promise<SyncAccepted> {
  // 202 Accepted: el trabajo corre en el backend; el progreso se sigue con getSyncStatus().
  const { data } = await api.post<SyncAccepted>('/sync', null, {
    params: { limit: 20, queues: '420,400' },
  })
  return data
}

export async function getSyncStatus(): Promise<SyncStatus> {
  const { data } = await api.get<SyncStatus>('/sync/status')
  return data
}

export async function getHealthStatus(): Promise<HealthStatus> {
  // El cliente añade /api al baseURL -> resuelve contra GET /api/health.
  const { data } = await api.get<HealthStatus>('/health')
  return data
}

// ───────────────────────── metadatos (Data Dragon vía backend) ─────────────────────────

export async function getChampionIndex(): Promise<ChampionsIndex> {
  const { data } = await api.get<ChampionsIndex>('/metadata/champions')
  return data
}

export async function getItemIndex(): Promise<ItemsIndex> {
  const { data } = await api.get<ItemsIndex>('/metadata/items')
  return data
}

export async function getSpellIndex(): Promise<SpellsIndex> {
  const { data } = await api.get<SpellsIndex>('/metadata/spells')
  return data
}

export async function getSettings(): Promise<UserSettings> {
  const { data } = await api.get<UserSettings>('/config')
  return data
}

export async function updateSettings(payload: UserSettingsUpdate): Promise<UserSettings> {
  const { data } = await api.put<UserSettings>('/config', payload)
  return data
}

export async function linkRiot(payload: RiotLinkRequest): Promise<UserSettings> {
  const { data } = await api.put<UserSettings>('/settings/riot', payload)
  return data
}

export async function updateMatchReview(gameId: string, review: MatchReviewUpdate): Promise<BackendMatch> {
  const { data } = await api.patch<BackendMatch>(`/matches/${gameId}`, review)
  return data
}

// ────────────────── ConstitutionStatus (shape diferente del backend) ──────────────────
// El frontend transforma la respuesta del backend en una forma más rica con reglas
// desglosadas y estadísticas. Este tipo NO viene del schema OpenAPI.

export interface ConstitutionRule {
  rule: string
  status: 'PASS' | 'FAIL'
  severity: 'pass' | 'fail' | 'warning'
  message: string
  detail: string
}

export interface ConstitutionStatus {
  global_status: string
  message: string
  rules: ConstitutionRule[]
  stats: {
    games_analyzed: number
    wins: number
    losses: number
    avg_deaths: number
    avg_cs_min: number
    consecutive_losses: number
  }
}

export async function getConstitutionStatus(): Promise<ConstitutionStatus> {
  const { data } = await api.get<ConstitutionStatus>('/constitution/status')
  return data
}

// ────────────────── LpTrendPoint (computado en el router, no es schema Pydantic) ──────

export interface LpTrendPoint {
  game_id: string
  date: string
  champion: string
  enemy_champion: string | null
  win: boolean
  lp_change: number | null
  has_lp: boolean
  lp_cumulative: number
}

export async function getLpTrend(limit = 30, queue?: number): Promise<LpTrendPoint[]> {
  const params: Record<string, number> = { limit }
  if (queue != null) params.queue = queue
  const { data } = await api.get<LpTrendPoint[]>('/stats/lp-trend', { params })
  return data
}

// ────────────────── ChampionPerf (alias del schema ChampionStats) ────────────────────

export type ChampionPerf = ChampionStats

export async function getChampionStats(): Promise<ChampionStats[]> {
  const { data } = await api.get<ChampionStats[]>('/stats/champions')
  return data
}

export async function getChampionRoleSummary(): Promise<ChampionRoleSummary[]> {
  const { data } = await api.get<ChampionRoleSummary[]>('/stats/champion-summary')
  return data
}

export async function getSessionFatigue(): Promise<SessionFatigue> {
  const { data } = await api.get<SessionFatigue>('/stats/session-fatigue')
  return data
}

export async function getScoutOpponent(gameId: string): Promise<ScoutOpponent> {
  const { data } = await api.get<ScoutOpponent>(`/matches/${encodeURIComponent(gameId)}/scout-opponent`)
  return data
}

export async function getMetaVerdict(): Promise<MetaVerdictResponse> {
  const { data } = await api.get<MetaVerdictResponse>('/stats/meta-verdict')
  return data
}

export async function getHeatmapStats(): Promise<HeatmapResponse> {
  const { data } = await api.get<HeatmapResponse>('/stats/heatmap')
  return data
}

export async function getPatchAlert(): Promise<PatchAlert> {
  const { data } = await api.get<PatchAlert>('/stats/patch-alert')
  return data
}

export async function getKpiTrends(limit = 50): Promise<TrendPoint[]> {
  const { data } = await api.get<TrendPoint[]>('/stats/trends', { params: { limit } })
  return data
}

export async function getLaningStats(limit = 50): Promise<LaningSummary> {
  const { data } = await api.get<LaningSummary>('/stats/laning', { params: { limit } })
  return data
}

export async function getWeeklyReport(): Promise<WeeklyReport> {
  const { data } = await api.get<WeeklyReport>('/stats/weekly')
  return data
}

// ─────────────────────────────── Matchups ───────────────────────────────

export async function getMatchupStats(
  userChampion: string,
  enemyChampion: string,
): Promise<MatchupStats> {
  const { data } = await api.get<MatchupStats>(
    `/stats/matchups/${encodeURIComponent(userChampion)}/${encodeURIComponent(enemyChampion)}`,
  )
  return data
}

export async function getMatchupNotes(
  userChampion: string,
  enemyChampion: string,
): Promise<MatchupNotes> {
  const { data } = await api.get<MatchupNotes>(
    `/matchup-notes/${encodeURIComponent(userChampion)}/${encodeURIComponent(enemyChampion)}`,
  )
  return data
}

export async function updateMatchupNotes(
  userChampion: string,
  enemyChampion: string,
  payload: MatchupNotesUpdate,
): Promise<MatchupNotes> {
  const { data } = await api.put<MatchupNotes>(
    `/matchup-notes/${encodeURIComponent(userChampion)}/${encodeURIComponent(enemyChampion)}`,
    payload,
  )
  return data
}
