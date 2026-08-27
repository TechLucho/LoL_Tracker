import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChampionsList from './ChampionsList'
import type { ChampionPerf } from '../api/client'

vi.mock('../hooks/useMetadata', () => ({
  useIcons: () => ({
    champion: () => ({ url: '', name: '' }),
    item: () => null,
    spell: () => null,
  }),
}))

const base: ChampionPerf = {
  champion: 'Ahri',
  games_played: 15,
  wins: 10,
  winrate: 66.7,
  kda_ratio: 4.2,
  avg_kills: 8,
  avg_deaths: 3,
  avg_assists: 7,
  avg_cs_min: 7.5,
  avg_dpm: 620,
}

describe('ChampionsList', () => {
  it('shows empty state when no champions', () => {
    render(<ChampionsList champions={[]} />)
    expect(screen.getByText(/Sincroniza partidas/)).toBeInTheDocument()
  })

  it('renders champion rows when data is present', () => {
    render(<ChampionsList champions={[base]} />)
    expect(screen.getByText('Ahri')).toBeInTheDocument()
    expect(screen.getByText('66.7%')).toBeInTheDocument()
  })

  it('shows shimmer while loading', () => {
    const { container } = render(<ChampionsList champions={[]} isLoading />)
    expect(container.querySelector('.shimmer')).toBeInTheDocument()
  })
})
