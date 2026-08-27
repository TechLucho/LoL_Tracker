import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RecordsCard from './RecordsCard'
import type { UIMatch } from '../data/types'

function makeMatch(overrides: Partial<UIMatch> = {}): UIMatch {
  return {
    game_id: 'TEST_001',
    date: '2026-08-27T14:00:00Z',
    champion: 'Ahri',
    role: 'MID',
    kills: 8, deaths: 3, assists: 12,
    cs_total: 187, cs_min: 7.2, control_wards: 2,
    win: true, enemy_champion: 'Yasuo',
    game_duration_minutes: 28.5,
    duration_display: '28:30',
    time_ago: '2h ago',
    spells: [14, 4],
    kda_ratio: 6.67, kill_participation: 0.72, dpm: 860,
    rating: 85, queue_id: 420,
    participants: null,
    lp_change: null, tilt_level: null,
    impact_rating: null, notes: null, vod_review: null,
    ...overrides,
  }
}

describe('RecordsCard', () => {
  it('shows empty state with no matches', () => {
    render(<RecordsCard matches={[]} />)
    expect(screen.getByText(/Sincroniza partidas/)).toBeInTheDocument()
  })

  it('renders records when matches are provided', () => {
    render(<RecordsCard matches={[makeMatch()]} />)
    expect(screen.getByText('Mejor Rating')).toBeInTheDocument()
  })
})
