// Tests del mapeo BackendMatch → UIMatch (useMatches.ts).
// Cubre el contrato anti-fantasía: las filas legacy (sin participants, sin duración) usan
// estimaciones declaradas y el dato real del backend SIEMPRE gana cuando existe.

import { describe, it, expect } from 'vitest'
import { mapBackendToUI } from './useMatches'
import type { BackendMatch, BackendParticipant } from '../data/types'

function backendMatch(overrides: Partial<BackendMatch> = {}): BackendMatch {
  return {
    game_id: 'EUW1_123',
    date: new Date(2026, 0, 1, 12).toISOString(),
    champion: 'Jinx',
    role: 'BOTTOM',
    kills: 10,
    deaths: 2,
    assists: 8,
    cs_total: 240,
    cs_min: 8,
    control_wards: 3,
    win: true,
    enemy_champion: 'Caitlyn',
    game_duration_minutes: 32.5,
    queue_id: 420,
    participants: null,
    lp_change: null,
    tilt_level: null,
    impact_rating: null,
    notes: null,
    vod_review: false,
    ...overrides,
  }
}

function participant(overrides: Partial<BackendParticipant> = {}): BackendParticipant {
  return {
    champion_name: 'Jinx',
    puuid: 'abc',
    player_name: 'lucho#EUW',
    kills: 10,
    deaths: 2,
    assists: 8,
    cs: 260,
    items: [1, 2, 3, 4, 5, 6, 7],
    summoner_spells: [7, 4],
    team_id: 100,
    team_position: 'BOTTOM',
    win: true,
    total_damage: 32000,
    total_damage_taken: 15000,
    gold_earned: 16000,
    vision_score: 25,
    kill_participation: 0.72,
    rating: 66,
    ...overrides,
  }
}

describe('mapBackendToUI — fila legacy (sin participants)', () => {
  it('usa duración por defecto 25 min y muestra --:-- si la duración es null', () => {
    const ui = mapBackendToUI(backendMatch({ participants: null, game_duration_minutes: null }))
    expect(ui.game_duration_minutes).toBe(25)
    expect(ui.duration_display).toBe('--:--')
  })

  it('estima DPM con la fórmula legacy declarada', () => {
    const ui = mapBackendToUI(backendMatch({ participants: null, game_duration_minutes: null }))
    // (10·450 + 8·250 + 8·25·3.2) / 25 = 285.6 → 286
    expect(ui.dpm).toBe(286)
  })

  it('estima KP y calcula rating local cuando no hay datos del backend', () => {
    const ui = mapBackendToUI(backendMatch({ participants: null }))
    // KP estimado: (10+8) / (18+3) = 0.857…
    expect(ui.kill_participation).toBeCloseTo(18 / 21)
    // Rating: 50 +15(victoria) +min(20,(9−2)·5)=+20 +min(10,(8−7)·3)=+3 +min(10,(0.857−0.5)·20)≈+7.14 −0(muertes<3) ≈ 95.14
    expect(ui.rating).toBeCloseTo(95.1, 1)
  })

  it('rellena enemy_champion Unknown y hechizos por defecto', () => {
    const ui = mapBackendToUI(backendMatch({ participants: null, enemy_champion: null }))
    expect(ui.enemy_champion).toBe('Unknown')
    expect(ui.spells).toEqual([12, 4])
  })

  it('KDA con 0 muertes es kills+assists', () => {
    const ui = mapBackendToUI(backendMatch({ participants: null, deaths: 0 }))
    expect(ui.kda_ratio).toBe(18)
  })
})

describe('mapBackendToUI — fila moderna (con participants)', () => {
  it('encuentra al jugador por campeón aunque el case difiera', () => {
    const me = participant({ champion_name: 'jinx' })
    const ui = mapBackendToUI(
      backendMatch({ participants: [participant({ champion_name: 'Thresh', puuid: 'sup' }), me] }),
    )
    expect(ui.rating).toBe(66)
    expect(ui.dpm).toBe(985) // round(32000 / 32.5)
    expect(ui.kill_participation).toBe(0.72)
  })

  it('el rating del backend GANA sobre la fórmula local (decisión 2026-08-21)', () => {
    const ui = mapBackendToUI(backendMatch({ participants: [participant({ rating: 42 })] }))
    expect(ui.rating).toBe(42)
  })

  it('DPM real sale de total_damage / duración real', () => {
    const ui = mapBackendToUI(
      backendMatch({ participants: [participant({ total_damage: 13000 })], game_duration_minutes: 26 }),
    )
    expect(ui.dpm).toBe(500)
  })

  it('formatea la duración real mm:ss', () => {
    const ui = mapBackendToUI(backendMatch({ game_duration_minutes: 32.5 }))
    expect(ui.duration_display).toBe('32:30')
  })

  it('usa los summoner spells reales y rellena huecos con Flash', () => {
    const ui = mapBackendToUI(backendMatch({ participants: [participant({ summoner_spells: [7] })] }))
    expect(ui.spells).toEqual([7, 4])
  })

  it('propaga los campos subjetivos sin tocarlos (nullable)', () => {
    const ui = mapBackendToUI(
      backendMatch({
        lp_change: -18,
        tilt_level: 4,
        impact_rating: 'S',
        notes: 'tilt total',
        vod_review: true,
      }),
    )
    expect(ui.lp_change).toBe(-18)
    expect(ui.tilt_level).toBe(4)
    expect(ui.impact_rating).toBe('S')
    expect(ui.notes).toBe('tilt total')
    expect(ui.vod_review).toBe(true)
  })
})
