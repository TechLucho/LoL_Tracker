// ──────────────── Tipos del backend (fuente de verdad: schemas.py vía OpenAPI) ────────────────
// Re-exportados desde api/generated.ts. Si el backend cambia un campo, estos se
// actualizan automáticamente con `python -m backend.scripts.export_openapi`.
export type {
  BackendMatch,
  BackendParticipant,
  MatchUpdate as MatchReviewUpdate,
  UserSettingsUpdate,
  TrendPoint,
  WeeklyReport,
  WeeklyTopChampion,
  WeeklyBestMatch,
} from '../api/generated'

// ──────────────── Tipos exclusivos del frontend ────────────────
// Estos tipos NO existen en el backend: son transformaciones o derivaciones para la UI.

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

export type QueueFilter = 'all' | 'ranked' | 'normal'

// ─────────────────────────── insights del Dashboard ───────────────────────────
// Calculados SIEMPRE sobre partidas sincronizadas reales (ver data/insights.ts).

export interface FormCheckMetric {
  name: string
  unit: string
  previous: number
  current: number
  /** true si bajar es mejorar (ej.: muertes por partida). */
  lowerIsBetter?: boolean
}

export interface RecordEntry {
  label: string
  value: string
  icon: string
}

export interface InsightNote {
  label: string
  winrate: number
  games: number
  /** Puntos de winrate respecto a la media global del historial mostrado. */
  comparison: number
  coaching: string
}
