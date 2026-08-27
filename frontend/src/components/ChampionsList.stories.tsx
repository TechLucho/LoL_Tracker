import type { Meta, StoryObj } from '@storybook/react-vite'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ChampionsList from './ChampionsList'
import type { ChampionPerf } from '../api/client'

const champions: ChampionPerf[] = [
  { champion: 'Ahri', games_played: 45, wins: 30, winrate: 66.7, kda_ratio: 4.2, avg_kills: 8, avg_deaths: 3, avg_assists: 7, avg_cs_min: 7.5, avg_dpm: 620 },
  { champion: 'Jinx', games_played: 32, wins: 18, winrate: 56.3, kda_ratio: 3.1, avg_kills: 10, avg_deaths: 5, avg_assists: 6, avg_cs_min: 8.1, avg_dpm: 710 },
  { champion: 'Thresh', games_played: 20, wins: 8, winrate: 40.0, kda_ratio: 2.0, avg_kills: 1, avg_deaths: 6, avg_assists: 14, avg_cs_min: 0.8, avg_dpm: 210 },
]

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ maxWidth: 320, background: '#0A0A0F', padding: 16 }}>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        {children}
      </QueryClientProvider>
    </div>
  )
}

const meta: Meta<typeof ChampionsList> = {
  title: 'Components/ChampionsList',
  component: ChampionsList,
  decorators: [(Story) => <Wrapper><Story /></Wrapper>],
}
export default meta
type Story = StoryObj<typeof ChampionsList>

export const Empty: Story = {
  args: { champions: [] },
}

export const Loading: Story = {
  args: { champions: [], isLoading: true },
}

export const WithData: Story = {
  args: { champions },
}
