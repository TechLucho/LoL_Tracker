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
// logout sin reiniciar la SPA. Se trackea `activeToken` para detectar 401s stale en la
// respuesta (requests en vuelo de una sesión anterior que resuelven tras re-login).
api.interceptors.request.use(async (config) => {
  try {
    const { data } = await supabase.auth.getSession()
    if (data.session?.access_token) {
      config.headers.set('Authorization', `Bearer ${data.session.access_token}`)
      activeToken = data.session.access_token
    } else {
      activeToken = null
    }
  } catch {
    // Sin Supabase configurado la sesión es nula: la petición sale sin token y el backend
    // responde 401 — nunca rompe el interceptor.
    activeToken = null
  }
  return config
})

// ───────────────────────── 401 global: sesión caducada/revocada ─────────────────────────
// Al detectar un 401 (token expirado, revocado o sin sesión) se cierra la sesión de Supabase,
// se vacía la caché de TanStack Query (nada de datos del usuario anterior en el caché) y se
// avisa. El redirect NO vive aquí: `supabase.auth.signOut()` dispara `onAuthStateChange` y el
// AuthProvider pone la sesión a null, con lo que RequireAuth redirige a /login conservando la
// ruta previa en `state.from`. Los 401 simultáneos (varias queries en vuelo) se colapsan en uno.
// Detección de stale: `queryClient.clear()` NO cancela HTTP requests en vuelo; cuando uno de
// esos requests stale responde 401 tras un re-login, comparamos el token de la petición con
// `activeToken` (el token actual) para ignorarlo y no matar la sesión fresca.

let handlingUnauthorized = false
// Token usado por el request más reciente. Permite detectar 401s "stale" de una sesión anterior
// que llegan después de que el usuario haya iniciado sesión con un token nuevo.
let activeToken: string | null = null

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

// Singleflight para refrescar la sesión: los 401 concurrentes comparten UN solo
// `refreshSession()` (el refresh_token de Supabase es de un solo uso — dos refrescos en
// paralelo invalidarían el segundo). La promesa devuelve el nuevo access_token o null si el
// refresh falló (sesión realmente revocada).
let refreshInFlight: Promise<string | null> | null = null

function refreshSessionToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = supabase.auth
      .refreshSession()
      .then(({ data }) => data.session?.access_token ?? null)
      .catch(() => null)
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

// El guard se rearma con cada login: si la nueva sesión vuelve a caducar, el aviso se repite.
// Además se refresca `activeToken` en los eventos de auth para cerrar la ventana en la que un
// 401 stale podría llegar justo tras el re-login, antes de que una petición nueva lo actualice.
// `INITIAL_SESSION` y `TOKEN_REFRESHED` también actualizan el token vigente: tras un refresh
// de Supabase el token anterior es inválido en el servidor y un 401 así no debe tratarse como
// caducidad de sesión.
supabase.auth.onAuthStateChange((event, session) => {
  if (event === 'SIGNED_IN' || event === 'INITIAL_SESSION' || event === 'TOKEN_REFRESHED') {
    handlingUnauthorized = false
    activeToken = session?.access_token ?? null
  }
  if (event === 'SIGNED_OUT') {
    activeToken = null
  }
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401 && error.config) {
      // Comparar el token de la petición fallida con el token de la sesión actual. Sólo se
      // considera 401 real el que rechaza el token vigente: un request stale (en vuelo de una
      // sesión anterior, o enviado sin token mientras ya no hay sesión) se ignora para no
      // matar la sesión fresca ni duplicar el toast de expiración.
      const raw = error.config.headers?.get?.('Authorization')
        ?? error.config.headers?.['Authorization']
      const failedToken = typeof raw === 'string' ? raw.replace(/^Bearer\s+/i, '') : null

      if (activeToken && failedToken === activeToken) {
        const config = error.config as typeof error.config & { __lolTrackerRetried?: boolean }

        // Un 401 CON token vigente puede ser transitorio: el token expiró segundos antes de
        // que el refresh automático de Supabase (timer) se ejecutara, o el arranque en frío
        // del PyJWKClient del backend tardó en validar. Antes de dar la sesión por muerta se
        // refresca la sesión y se reintenta UNA vez con el token fresco.
        if (!config.__lolTrackerRetried) {
          config.__lolTrackerRetried = true
          const newToken = await refreshSessionToken()
          if (newToken) {
            config.headers.set('Authorization', `Bearer ${newToken}`)
            // El request interceptor re-lee la sesión y actualiza activeToken; el retry sale
            // con el token nuevo. Si vuelve a fallar con 401, cae en el handleUnauthorized.
            return api(config)
          }
        }
        handleUnauthorized()
      }
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

// ───────────────────────── El Rosco (Sprint 1 backend) ─────────────────────────
// El contrato OpenAPI generado aún no incluye /api/games/* (se regenerará en el Sprint que
// lo consuma desde el backend); el tipo se declara a mano, igual que `LpTrendPoint`.

export type GameRoomStatus = 'lobby' | 'drafting' | 'minigames' | 'rosco' | 'finished'

export interface GameRoom {
  id: string
  room_code: string
  host_id: string
  guest_id: string | null
  status: GameRoomStatus
  created_at: string
  winner_id: string | null
}

export async function createGameRoom(): Promise<GameRoom> {
  const { data } = await api.post<GameRoom>('/games/rooms')
  return data
}

export async function joinGameRoom(roomCode: string): Promise<GameRoom> {
  const { data } = await api.post<GameRoom>(
    `/games/rooms/${encodeURIComponent(roomCode)}/join`,
  )
  return data
}

// ──────────────────── El Rosco (Sprint 3 backend: draft y minijuegos) ────────────────────
// Estado vivo que el backend (árbitro) difunde por Realtime y devuelve en cada mutación.
// `draft_turn` = a quién le toca elegir ('host' primero); los bancos clave son 100s base +
// segundos ganados por cada jugador (Regla 3 del CHECKLIST).

export type RoomRole = 'host' | 'guest'

export interface GameLiveState {
  room_code: string
  status: GameRoomStatus
  draft_turn: RoomRole | null
  draft_picks: Partial<Record<RoomRole, string>>
  time_banks: Partial<Record<RoomRole, number>>
}

export interface GameStateInput {
  status: GameRoomStatus
}

export interface DraftPickInput {
  category: string
}

export interface ScoreInput {
  points: number
}

export async function advanceGameState(roomCode: string, status: GameRoomStatus): Promise<GameLiveState> {
  const { data } = await api.post<GameLiveState>(
    `/games/rooms/${encodeURIComponent(roomCode)}/state`,
    { status } satisfies GameStateInput,
  )
  return data
}

export async function draftPick(roomCode: string, category: string): Promise<GameLiveState> {
  const { data } = await api.post<GameLiveState>(
    `/games/rooms/${encodeURIComponent(roomCode)}/draft`,
    { category } satisfies DraftPickInput,
  )
  return data
}

export async function submitScore(roomCode: string, points: number): Promise<GameLiveState> {
  const { data } = await api.post<GameLiveState>(
    `/games/rooms/${encodeURIComponent(roomCode)}/score`,
    { points } satisfies ScoreInput,
  )
  return data
}

// ──────────────────── El Rosco (Sprint 4 backend: motor y turnos) ────────────────────
// Contrato del estado completo del Rosco que devuelven answer/timeout y difunden los
// broadcasts `rosco` / `game_over`. `current_turn` None = nadie puede jugar (partida acabada);
// `winner` None con `draw` False solo mientras la partida sigue en curso.

export type RoscoLetterStatus = 'pending' | 'success' | 'failed'

export interface RoscoLetter {
  letter: string
  question: string
  status: RoscoLetterStatus
}

export interface RoscoPlayerState {
  time_remaining: number
  letters: RoscoLetter[]
}

export interface RoscoState {
  room_code: string
  status: GameRoomStatus
  current_turn: RoomRole | null
  players: Record<RoomRole, RoscoPlayerState>
  winner: RoomRole | null
  draw: boolean
}

export interface RoscoAnswerInput {
  letter: string
  answer: string
  time_remaining?: number
}

export async function roscoAnswer(roomCode: string, payload: RoscoAnswerInput): Promise<RoscoState> {
  const { data } = await api.post<RoscoState>(
    `/games/rooms/${encodeURIComponent(roomCode)}/rosco/answer`,
    payload,
  )
  return data
}

export async function roscoTimeout(roomCode: string): Promise<RoscoState> {
  const { data } = await api.post<RoscoState>(
    `/games/rooms/${encodeURIComponent(roomCode)}/rosco/timeout`,
  )
  return data
}
