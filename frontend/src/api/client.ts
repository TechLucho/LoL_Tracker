import axios from 'axios'
import type { BackendMatch, SyncAccepted, SyncStatus, UserSettings, UserSettingsUpdate, MatchReviewUpdate } from '../data/types'

// Producción: la URL deja de estar hardcodeada (VITE_API_URL en el build del hosting) y cae
// al origen de desarrollo local si no está definida.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
})

// Auth: si el backend tiene APP_API_TOKEN, cada petición lleva X-API-Token. Precedencia:
// variable de entorno del build > localStorage (clave lol_tracker.api_token), que permite
// rotar el token sin recompilar. Se lee en cada petición a propósito, no al arrancar.
api.interceptors.request.use((config) => {
  const token = import.meta.env.VITE_API_TOKEN ?? localStorage.getItem('lol_tracker.api_token')
  if (token) {
    config.headers.set('X-API-Token', token)
  }
  return config
})

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

export interface HealthStatus {
  status: 'ok' | 'degraded'
  database: boolean
  riot_key_present: boolean
  warnings: string[]
}

export async function getHealthStatus(): Promise<HealthStatus> {
  // El cliente añade /api al baseURL -> resuelve contra GET /api/health.
  const { data } = await api.get<HealthStatus>('/health')
  return data
}

// ───────────────────────── metadatos (Data Dragon vía backend) ─────────────────────────

export interface ChampionMeta {
  /** Id de Data Dragon ('LeeSin'), clave del diccionario. */
  id: string
  /** Nombre visible ('Lee Sin') — el mismo que guardan matches.champion / participant.champion_name. */
  name: string
  title: string
  description: string
  image: string
}

export interface ItemMeta {
  id: number
  name: string
  description: string
  image: string
}

export interface SpellMeta {
  id: number
  name: string
  description: string
  image: string
}

export interface ChampionsIndex {
  patch: string
  champions: Record<string, ChampionMeta>
}

export interface ItemsIndex {
  patch: string
  items: Record<string, ItemMeta>
}

export interface SpellsIndex {
  patch: string
  spells: Record<string, SpellMeta>
}

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

export async function updateMatchReview(gameId: string, review: MatchReviewUpdate): Promise<BackendMatch> {
  const { data } = await api.patch<BackendMatch>(`/matches/${gameId}`, review)
  return data
}

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

export interface ChampionPerf {
  champion: string
  games_played: number
  wins: number
  winrate: number
  avg_kills: number
  avg_deaths: number
  avg_assists: number
  kda_ratio: number
  avg_cs_min: number
  avg_dpm: number
}

export async function getChampionStats(): Promise<ChampionPerf[]> {
  const { data } = await api.get<ChampionPerf[]>('/stats/champions')
  return data
}

export interface HeatmapCell {
  day_of_week: number
  time_block: string
  games_played: number
  wins: number
  losses: number
  winrate: number
}

export async function getHeatmapStats(): Promise<HeatmapCell[]> {
  const { data } = await api.get<HeatmapCell[]>('/stats/heatmap')
  return data
}
