export interface BackendParticipant {
  champion_name: string
  puuid: string
  player_name: string
  kills: number
  deaths: number
  assists: number
  cs: number
  items: number[]
  summoner_spells: number[]
  team_id: number
  team_position: string
  win: boolean
  total_damage: number
  total_damage_taken: number
  gold_earned: number
  vision_score: number
  kill_participation: number
  rating: number
  rating_version?: number
}

export interface BackendMatch {
  game_id: string
  date: string
  champion: string
  role: string
  kills: number
  deaths: number
  assists: number
  cs_total: number
  cs_min: number
  control_wards: number
  win: boolean
  enemy_champion: string | null
  game_duration_minutes: number | null
  queue_id: number | null
  participants: BackendParticipant[] | null
  lp_change: number | null
  tilt_level: number | null
  impact_rating: string | null
  notes: string | null
  vod_review: boolean | null
}

export interface UIParticipant {
  champion_name: string
  puuid: string
  player_name: string
  kills: number
  deaths: number
  assists: number
  cs: number
  items: number[]
  summoner_spells: number[]
  team_id: number
  team_position: string
  win: boolean
  total_damage: number
  total_damage_taken: number
  gold_earned: number
  vision_score: number
  kill_participation: number
  rating: number
}

export interface UIMatch {
  game_id: string
  date: string
  champion: string
  role: string
  kills: number
  deaths: number
  assists: number
  cs_total: number
  cs_min: number
  control_wards: number
  win: boolean
  enemy_champion: string
  game_duration_minutes: number
  duration_display: string
  time_ago: string
  spells: [number, number]
  kda_ratio: number
  kill_participation: number
  dpm: number
  rating: number
  queue_id: number | null
  participants: UIParticipant[] | null
  lp_change: number | null
  tilt_level: number | null
  impact_rating: string | null
  notes: string | null
  vod_review: boolean | null
}

export interface LpCapture {
  lp: number
  tier: string | null
  division: string | null
  delta_assigned: number | null
}

export interface SyncResult {
  fetched: number
  inserted: number
  skipped: number
  errors: Array<{ game_id: string; reason: string; retryable: boolean }>
  lp_captured?: LpCapture | null
}

export interface SyncAccepted {
  status: 'processing'
  message: string
}

export interface SyncStatus {
  status: 'idle' | 'processing' | 'success' | 'error'
  started_at: string | null
  finished_at: string | null
  result: SyncResult | null
  error: string | null
}

export type QueueFilter = 'all' | 'ranked' | 'normal'

export interface UserSettings {
  champion_pool: string[]
  target_cs_min: number
  max_deaths: number
  updated_at: string | null
  impact_ratings: string[]
  regions: string[]
  champion_pool_max: number
  display_timezone: string
  riot_id: string
  riot_region: string
}

export interface UserSettingsUpdate {
  champion_pool: string[]
  target_cs_min: number
  max_deaths: number
}

export interface MatchReviewUpdate {
  lp_change?: number | null
  tilt_level?: number | null
  impact_rating?: string | null
  notes?: string | null
  vod_review?: boolean | null
}

// ─────────────────────────── insights del Dashboard ───────────────────────────
// Calculados SIEMPRE sobre partidas sincronizadas reales (ver data/insights.ts).
// Los antiguos venían de mock.ts y mentían por diseño.

// Promedio de una estadística comparando dos ventanas de partidas (últimas 5 vs 5 anteriores).
export interface FormCheckMetric {
  name: string
  unit: string
  previous: number
  current: number
  /** true si bajar es mejorar (ej.: muertes por partida). */
  lowerIsBetter?: boolean
}

// Récord personal derivado del historial cargado.
export interface RecordEntry {
  label: string
  value: string
  icon: string
}

// Patrón de rendimiento (franja horaria, estado de racha previa…).
export interface InsightNote {
  label: string
  winrate: number
  games: number
  /** Puntos de winrate respecto a la media global del historial mostrado. */
  comparison: number
  coaching: string
}
