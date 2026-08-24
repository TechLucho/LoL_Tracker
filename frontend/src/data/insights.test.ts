// Tests unitarios de la lógica pura del Dashboard (data/insights.ts).
// Sin red, sin DOM, sin mocks de React: entrada UIMatch[] → salida verificable.
// El anti-mentira del proyecto se verifica aquí: muestra insuficiente ⇒ null/hueco, jamás invención.

import { describe, it, expect } from 'vitest'
import { computeFormCheck, metricTrend, computeRecords, computePerformanceNotes } from './insights'
import type { FormCheckGroups } from './insights'
import type { UIMatch, FormCheckMetric } from './types'

let seq = 0

function makeMatch(overrides: Partial<UIMatch> = {}): UIMatch {
  seq += 1
  // Hora local fija (12:00) convertida a ISO y re-parseada: getHours() da 12 en cualquier TZ.
  const date = new Date(2026, 0, 1, 12).toISOString()
  return {
    game_id: `EUW1_${seq}`,
    date,
    champion: 'Jinx',
    role: 'BOTTOM',
    kills: 5,
    deaths: 3,
    assists: 7,
    cs_total: 240,
    cs_min: 8,
    control_wards: 2,
    win: true,
    enemy_champion: 'Caitlyn',
    game_duration_minutes: 30,
    duration_display: '30:00',
    time_ago: '1d ago',
    spells: [4, 12],
    kda_ratio: 4,
    kill_participation: 0.6,
    dpm: 700,
    rating: 70,
    queue_id: 420,
    participants: null,
    lp_change: 15,
    tilt_level: null,
    impact_rating: null,
    notes: null,
    vod_review: false,
    ...overrides,
  }
}

function byName(groups: FormCheckGroups, name: string): FormCheckMetric {
  const all = [...groups.improving, ...groups.slipping, ...groups.steady]
  const metric = all.find((m) => m.name === name)
  if (!metric) throw new Error(`Métrica ${name} no encontrada`)
  return metric
}

describe('metricTrend', () => {
  it('clasifica up/down según el umbral ±2%', () => {
    expect(metricTrend({ name: 'DPM', unit: '', previous: 100, current: 103 })).toBe('up')
    expect(metricTrend({ name: 'DPM', unit: '', previous: 100, current: 97 })).toBe('down')
    expect(metricTrend({ name: 'DPM', unit: '', previous: 100, current: 101 })).toBe('flat')
    expect(metricTrend({ name: 'DPM', unit: '', previous: 100, current: 102 })).toBe('flat')
  })

  it('invierte la dirección cuando bajar es mejorar (muertes)', () => {
    expect(metricTrend({ name: 'Muertes/partida', unit: '', previous: 5, current: 4, lowerIsBetter: true })).toBe('up')
    expect(metricTrend({ name: 'Muertes/partida', unit: '', previous: 4, current: 5, lowerIsBetter: true })).toBe('down')
  })

  it('devuelve flat cuando previous es 0 en vez de dividir por cero', () => {
    expect(metricTrend({ name: 'KP%', unit: '%', previous: 0, current: 50 })).toBe('flat')
  })
})

describe('computeFormCheck', () => {
  it('devuelve null con muestra insuficiente (<8 partidas)', () => {
    expect(computeFormCheck([])).toBeNull()
    expect(computeFormCheck(Array.from({ length: 7 }, () => makeMatch()))).toBeNull()
  })

  it('compara las últimas 5 contra las anteriores (más-reciente-primero)', () => {
    const current = Array.from({ length: 5 }, () => makeMatch({ dpm: 800 }))
    const previous = Array.from({ length: 5 }, () => makeMatch({ dpm: 600 }))
    const groups = computeFormCheck([...current, ...previous])
    expect(groups).not.toBeNull()
    const dpm = byName(groups!, 'DPM')
    expect(dpm.current).toBe(800)
    expect(dpm.previous).toBe(600)
  })

  it('las muertes que bajan cuentan como mejora aunque el número baje', () => {
    const current = Array.from({ length: 5 }, () => makeMatch({ deaths: 2 }))
    const previous = Array.from({ length: 5 }, () => makeMatch({ deaths: 6 }))
    const groups = computeFormCheck([...current, ...previous])!
    const deaths = byName(groups, 'Muertes/partida')
    expect(deaths.current).toBe(2)
    expect(deaths.previous).toBe(6)
    expect(groups.improving.map((m) => m.name)).toContain('Muertes/partida')
  })

  it('redondea métricas a 1 decimal', () => {
    const current = [
      makeMatch({ dpm: 700 }),
      makeMatch({ dpm: 701 }),
      makeMatch({ dpm: 700 }),
      makeMatch({ dpm: 702 }),
      makeMatch({ dpm: 700 }),
    ]
    const previous = Array.from({ length: 5 }, () => makeMatch({ dpm: 700 }))
    const dpm = byName(computeFormCheck([...current, ...previous])!, 'DPM')
    expect(dpm.current).toBe(700.6)
  })

  it('funciona justo en el mínimo de muestra (8 partidas)', () => {
    // Ventana previa incompleta pero válida (3 partidas): 2/3 ≈ 66.7%. No se usa 0/3 porque
    // metricTrend fuerza flat cuando previous === 0 (guarda anti-división-cero documentada).
    const current = Array.from({ length: 5 }, () => makeMatch({ win: true }))
    const previous = [makeMatch({ win: true }), makeMatch({ win: true }), makeMatch({ win: false })]
    const groups = computeFormCheck([...current, ...previous])
    expect(groups).not.toBeNull()
    expect(byName(groups!, 'Win Rate').current).toBe(100)
    expect(byName(groups!, 'Win Rate').previous).toBeCloseTo(66.7)
    expect(groups!.improving.map((m) => m.name)).toContain('Win Rate')
    expect(groups!.slipping.map((m) => m.name)).not.toContain('Win Rate')
  })

  it('clasifica una mala racha actual en slipping', () => {
    const current = Array.from({ length: 5 }, () => makeMatch({ win: false }))
    const previous = Array.from({ length: 5 }, () => makeMatch({ win: true }))
    const groups = computeFormCheck([...current, ...previous])!
    expect(groups.slipping.map((m) => m.name)).toContain('Win Rate')
    expect(groups.improving.map((m) => m.name)).not.toContain('Win Rate')
  })

  it('deja Win Rate en steady cuando no hay cambio real', () => {
    // Ambas ventanas con 3/5 victorias: delta 0% ⇒ flat; el ruido no debe pintarse como mejora.
    const ventana = Array.from({ length: 5 }, (_, i) => makeMatch({ win: i < 3 }))
    const groups = computeFormCheck([...ventana, ...ventana])!
    expect(groups.steady.map((m) => m.name)).toContain('Win Rate')
    expect(groups.improving.map((m) => m.name)).not.toContain('Win Rate')
    expect(groups.slipping.map((m) => m.name)).not.toContain('Win Rate')
  })
})

describe('computeRecords', () => {
  it('devuelve [] sin historial', () => {
    expect(computeRecords([])).toEqual([])
  })

  it('extrae los récords reales del historial cargado', () => {
    const records = computeRecords([
      makeMatch({ rating: 55, kills: 2, dpm: 500, kill_participation: 0.4, kda_ratio: 1.2 }),
      makeMatch({ rating: 90, kills: 20, dpm: 1234.6, kill_participation: 0.8, kda_ratio: 12 }),
      makeMatch({ rating: 60, kills: 5, dpm: 600, kill_participation: 0.5, kda_ratio: 2.5 }),
    ])
    const valueOf = (label: string) => records.find((r) => r.label === label)?.value
    expect(valueOf('Mejor Rating')).toBe('90.0')
    expect(valueOf('Más Kills')).toBe('20')
    expect(valueOf('Mejor DPM')).toBe('1235')
    expect(valueOf('Mejor KP')).toBe('80%')
    expect(valueOf('Peor Partida')).toBe('1.20 KDA')
  })

  it('calcula la mejor racha respetendo el orden cronológico (input viene al revés)', () => {
    const w = () => makeMatch({ win: true })
    const l = () => makeMatch({ win: false })
    const streakOf = (newestFirst: UIMatch[]) =>
      computeRecords(newestFirst).find((r) => r.label === 'Mejor Racha')?.value

    // cronológico: W L W W W → racha final de 3
    expect(streakOf([w(), w(), w(), l(), w()])).toBe('3W')
    // cronológico: L L L L → 0
    expect(streakOf([l(), l(), l(), l()])).toBe('0W')
    // cronológico: W L W L → alternada, la mejor racha es 1 aunque acabe en L
    expect(streakOf([l(), w(), l(), w()])).toBe('1W')
  })
})

describe('computePerformanceNotes', () => {
  it('devuelve [] sin historial', () => {
    expect(computePerformanceNotes([])).toEqual([])
  })

  it('sólo cuenta partidas jugadas DESPUÉS de una racha de 2+', () => {
    // cronológico: L L W | W W → tras-2-derrotas = [3ª], tras-2-victorias = [5ª]
    const chrono = [
      makeMatch({ win: false }),
      makeMatch({ win: false }),
      makeMatch({ win: true, dpm: 900 }),
      makeMatch({ win: true }),
      makeMatch({ win: true, dpm: 300 }),
    ]
    const notes = computePerformanceNotes([...chrono].reverse())
    const afterLosses = notes.find((n) => n.label === 'Tras 2 Derrotas')
    const afterWins = notes.find((n) => n.label === 'Tras 2 Victorias')
    expect(afterLosses?.games).toBe(1)
    expect(afterLosses?.winrate).toBe(100)
    expect(afterWins?.games).toBe(1)
    expect(afterWins?.winrate).toBe(100)
  })

  it('agrupa franjas horarias locales y omite las vacías', () => {
    const morning = (id: string, wr: boolean) =>
      makeMatch({ game_id: id, date: new Date(2026, 0, 2, 9).toISOString(), win: wr })
    const afternoon = (id: string, wr: boolean) =>
      makeMatch({ game_id: id, date: new Date(2026, 0, 2, 15).toISOString(), win: wr })
    const night = (id: string, wr: boolean) =>
      makeMatch({ game_id: id, date: new Date(2026, 0, 2, 23).toISOString(), win: wr })

    const matches = [
      morning('m1', true),
      morning('m2', false),
      afternoon('t1', true),
      night('n1', false),
      night('n2', true),
      night('n3', false),
    ]
    // Input más-reciente-primero (contrato de /api/matches); cronológico: W L W L W L,
    // sin rachas de 2 ⇒ los cubos de racha deben quedar fuera.
    const notes = computePerformanceNotes([...matches].reverse())
    const labels = notes.map((n) => n.label)
    expect(labels).toContain('Mañana (06-14)')
    expect(labels).toContain('Tarde (14-20)')
    expect(labels).toContain('Noche (20-06)')
    expect(labels).not.toContain('Tras 2 Victorias')
    expect(labels).not.toContain('Tras 2 Derrotas')

    const morningNote = notes.find((n) => n.label === 'Mañana (06-14)')!
    expect(morningNote.games).toBe(2)
    expect(morningNote.winrate).toBe(50)

    // comparison = winrate de la franja − winrate global (3/6 = 50%)
    const nightNote = notes.find((n) => n.label === 'Noche (20-06)')!
    expect(nightNote.comparison).toBe(-16.7)
  })

  it('la madrugada (00-06) pertenece a la noche', () => {
    const matches = [makeMatch({ date: new Date(2026, 0, 2, 3).toISOString(), win: true })]
    const labels = computePerformanceNotes(matches).map((n) => n.label)
    expect(labels).toContain('Noche (20-06)')
    expect(labels).not.toContain('Mañana (06-14)')
  })
})
