// Cálculo de los insights del Dashboard a partir del historial REAL sincronizado.
// Sustituye a mock.ts: aquí no hay datos inventados. Si una métrica no tiene muestra
// suficiente, se omite o se piden más partidas — nunca se rellena con fantasía.

import type { UIMatch, FormCheckMetric, RecordEntry, InsightNote } from './types'

function avg(values: number[]): number {
  if (values.length === 0) return 0
  return values.reduce((sum, v) => sum + v, 0) / values.length
}

function winrateOf(games: UIMatch[]): number {
  return games.length === 0 ? 0 : (games.filter((m) => m.win).length / games.length) * 100
}

// matches llega más-reciente-primero desde /api/matches; el orden cronológico es reverse().
function chronological(matches: UIMatch[]): UIMatch[] {
  return [...matches].reverse()
}

/** Racha de victorias más larga dentro del historial cargado (orden cronológico). */
function longestWinStreak(games: UIMatch[]): number {
  let best = 0
  let current = 0
  for (const m of games) {
    current = m.win ? current + 1 : 0
    best = Math.max(best, current)
  }
  return best
}

// ─────────────────────────────── Form Check ───────────────────────────────

const FORM_CHECK_WINDOW = 5
// Mínimo para comparar: ventana actual completa + al menos 3 partidas de referencia.
const FORM_CHECK_MIN = FORM_CHECK_WINDOW + 3

interface WindowStats {
  winrate: number
  kda: number
  csMin: number
  deaths: number
  kp: number
  wards: number
  dpm: number
}

function windowStats(games: UIMatch[]): WindowStats {
  return {
    winrate: winrateOf(games),
    kda: avg(games.map((m) => m.kda_ratio)),
    csMin: avg(games.map((m) => m.cs_min)),
    deaths: avg(games.map((m) => m.deaths)),
    kp: avg(games.map((m) => m.kill_participation)) * 100,
    wards: avg(games.map((m) => m.control_wards)),
    dpm: avg(games.map((m) => m.dpm)),
  }
}

const FORM_CHECK_DEFS: Array<{
  key: keyof WindowStats
  name: string
  unit: string
  lowerIsBetter?: boolean
}> = [
  { key: 'winrate', name: 'Win Rate', unit: '%' },
  { key: 'kda', name: 'KDA', unit: '' },
  { key: 'kp', name: 'KP%', unit: '%' },
  { key: 'csMin', name: 'CS/min', unit: '' },
  { key: 'deaths', name: 'Muertes/partida', unit: '', lowerIsBetter: true },
  { key: 'wards', name: 'Control Wards', unit: '' },
  { key: 'dpm', name: 'DPM', unit: '' },
]

export interface FormCheckGroups {
  improving: FormCheckMetric[]
  slipping: FormCheckMetric[]
  steady: FormCheckMetric[]
}

/** Tendencia real de una métrica: mejorar/empeorar/estable, respetando la dirección deseada. */
export function metricTrend(metric: FormCheckMetric): 'up' | 'down' | 'flat' {
  const deltaPct =
    metric.previous === 0 ? 0 : ((metric.current - metric.previous) / metric.previous) * 100
  const effective = metric.lowerIsBetter ? -deltaPct : deltaPct
  if (effective > 2) return 'up'
  if (effective < -2) return 'down'
  return 'flat'
}

/**
 * Compara las últimas 5 partidas con las 5 anteriores. Devuelve null si no hay muestra
 * suficiente para comparar sin engañarse con ruido.
 */
export function computeFormCheck(matches: UIMatch[]): FormCheckGroups | null {
  if (matches.length < FORM_CHECK_MIN) return null

  const currentGames = matches.slice(0, FORM_CHECK_WINDOW)
  const previousGames = matches.slice(FORM_CHECK_WINDOW, FORM_CHECK_WINDOW * 2)
  if (previousGames.length === 0) return null

  const current = windowStats(currentGames)
  const previous = windowStats(previousGames)

  const groups: FormCheckGroups = { improving: [], slipping: [], steady: [] }
  for (const def of FORM_CHECK_DEFS) {
    const metric: FormCheckMetric = {
      name: def.name,
      unit: def.unit,
      lowerIsBetter: def.lowerIsBetter,
      previous: +previous[def.key].toFixed(1),
      current: +current[def.key].toFixed(1),
    }
    const trend = metricTrend(metric)
    const bucket = trend === 'up' ? groups.improving : trend === 'down' ? groups.slipping : groups.steady
    bucket.push(metric)
  }
  return groups
}

// ──────────────────────────────── Records ────────────────────────────────

export function computeRecords(matches: UIMatch[]): RecordEntry[] {
  if (matches.length === 0) return []

  const bestBy = (pick: (m: UIMatch) => number): UIMatch =>
    matches.reduce((best, m) => (pick(m) > pick(best) ? m : best), matches[0])

  const bestRating = bestBy((m) => m.rating)
  const mostKills = bestBy((m) => m.kills)
  const bestDpm = bestBy((m) => m.dpm)
  const bestKp = bestBy((m) => m.kill_participation)
  const worstGame = matches.reduce(
    (worst, m) => (m.kda_ratio < worst.kda_ratio ? m : worst),
    matches[0],
  )
  // Nota honesta: en filas legacy (sin participants) `dpm` es la estimación antigua,
  // la misma que muestra el accordion para esas partidas.
  const streak = longestWinStreak(chronological(matches))

  return [
    { label: 'Mejor Rating', value: bestRating.rating.toFixed(1), icon: 'trophy' },
    { label: 'Más Kills', value: String(mostKills.kills), icon: 'swords' },
    { label: 'Mejor DPM', value: String(Math.round(bestDpm.dpm)), icon: 'flame' },
    { label: 'Mejor KP', value: `${Math.round(bestKp.kill_participation * 100)}%`, icon: 'target' },
    { label: 'Mejor Racha', value: `${streak}W`, icon: 'zap' },
    { label: 'Peor Partida', value: `${worstGame.kda_ratio.toFixed(2)} KDA`, icon: 'skull' },
  ]
}

// ──────────────────────────── Performance Notes ───────────────────────────

interface NoteDef {
  label: string
  games: UIMatch[]
  coaching: string
}

export function computePerformanceNotes(matches: UIMatch[]): InsightNote[] {
  if (matches.length === 0) return []

  const overall = winrateOf(matches)
  const chrono = chronological(matches)

  // Partidas jugadas inmediatamente después de una racha de 2+ victorias / 2+ derrotas.
  const afterTwoWins: UIMatch[] = []
  const afterTwoLosses: UIMatch[] = []
  let runWon: boolean | null = null
  let runLen = 0
  for (let i = 0; i < chrono.length; i++) {
    if (i > 0 && runLen >= 2 && runWon !== null) {
      ;(runWon ? afterTwoWins : afterTwoLosses).push(chrono[i])
    }
    const won = chrono[i].win
    if (runWon === won) {
      runLen += 1
    } else {
      runWon = won
      runLen = 1
    }
  }

  // Franjas horarias en hora local del navegador (para este usuario = DISPLAY_TIMEZONE).
  const hourOf = (m: UIMatch) => new Date(m.date).getHours()
  const morning = matches.filter((m) => {
    const h = hourOf(m)
    return h >= 6 && h < 14
  })
  const afternoon = matches.filter((m) => {
    const h = hourOf(m)
    return h >= 14 && h < 20
  })
  const night = matches.filter((m) => {
    const h = hourOf(m)
    return h >= 20 || h < 6
  })

  const defs: NoteDef[] = [
    { label: 'Tras 2 Victorias', games: afterTwoWins, coaching: 'Cómo rindes con la moral alta' },
    { label: 'Tras 2 Derrotas', games: afterTwoLosses, coaching: 'Tu recuperación tras un bache' },
    { label: 'Mañana (06-14)', games: morning, coaching: 'Partidas de primera hora' },
    { label: 'Tarde (14-20)', games: afternoon, coaching: 'Partidas de media tarde' },
    { label: 'Noche (20-06)', games: night, coaching: 'Vigila la fatiga nocturna' },
  ]

  // Sin muestra (0 partidas en la franja/racha) no se muestra nada: mejor un hueco que una mentira.
  return defs
    .filter((d) => d.games.length > 0)
    .map((d) => {
      const wr = winrateOf(d.games)
      return {
        label: d.label,
        winrate: wr,
        games: d.games.length,
        comparison: +(wr - overall).toFixed(1),
        coaching: d.coaching,
      }
    })
}
