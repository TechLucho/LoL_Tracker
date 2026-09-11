import { describe, it, expect } from 'vitest'
import { computeOkrResults } from './okr'
import type { UIMatch, UIParticipant } from './types'

const targets = { target_dpm: 500, target_kp_percent: 50, target_vision_score: 20 }

const me: UIParticipant = {
  champion_name: 'Ahri',
  puuid: 'p1',
  player_name: 'Lucho#EUW',
  kills: 8,
  deaths: 3,
  assists: 7,
  cs: 200,
  items: [],
  summoner_spells: [],
  team_id: 100,
  team_position: 'MIDDLE',
  win: true,
  total_damage: 0,
  total_damage_taken: 0,
  gold_earned: 12000,
  vision_score: 34,
  kill_participation: 0.6,
  rating: 75,
}

function makeMatch(overrides: Partial<UIMatch> = {}): UIMatch {
  return {
    game_id: 'EUW1_1',
    date: '2026-01-01T12:00:00Z',
    champion: 'Ahri',
    role: 'MIDDLE',
    kills: 8,
    deaths: 3,
    assists: 7,
    cs_total: 200,
    cs_min: 7.5,
    control_wards: 2,
    win: true,
    enemy_champion: 'Zed',
    game_duration_minutes: 30,
    duration_display: '30:00',
    time_ago: 'hace 2h',
    spells: [4, 7],
    kda_ratio: 5,
    kill_participation: 0.6,
    dpm: 620,
    rating: 75,
    queue_id: 420,
    participants: [me],
    lp_change: null,
    tilt_level: null,
    impact_rating: null,
    notes: null,
    vod_review: false,
    ...overrides,
  }
}

describe('computeOkrResults', () => {
  it('marca OK los objetivos cumplidos', () => {
    const results = computeOkrResults(me, makeMatch(), targets)
    expect(results.every((r) => r.met)).toBe(true)
    expect(results.map((r) => r.current)).toEqual([620, 60, 34])
  })

  it('marca fallo cuando el DPM no alcanza la meta', () => {
    const results = computeOkrResults(me, makeMatch({ dpm: 400 }), targets)
    expect(results.find((r) => r.label === 'DPM')?.met).toBe(false)
    expect(results.find((r) => r.label === 'DPM')?.current).toBe(400)
  })

  it('convierte kill_participation (ratio 0-1) a porcentaje antes de comparar', () => {
    const results = computeOkrResults(
      me,
      makeMatch({ kill_participation: 0.45 }),
      targets,
    )
    expect(results.find((r) => r.label === 'KP%')?.met).toBe(false)
    expect(results.find((r) => r.label === 'KP%')?.current).toBe(45)
  })

  it('marca fallo de visión con vision_score bajo', () => {
    const lowVision = { ...me, vision_score: 12 }
    const results = computeOkrResults(lowVision, makeMatch(), targets)
    expect(results.find((r) => r.label === 'Visión')?.met).toBe(false)
  })
})