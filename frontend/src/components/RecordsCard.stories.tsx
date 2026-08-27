import type { Meta, StoryObj } from '@storybook/react-vite'
import RecordsCard from './RecordsCard'
import type { UIMatch } from '../data/types'

function makeMatch(overrides: Partial<UIMatch> = {}): UIMatch {
  return {
    game_id: 'TEST_001', date: '2026-08-27T14:00:00Z', champion: 'Ahri', role: 'MID',
    kills: 12, deaths: 2, assists: 8, cs_total: 220, cs_min: 8.5, control_wards: 4,
    win: true, enemy_champion: 'Yasuo', game_duration_minutes: 32, duration_display: '32:00',
    time_ago: '2h', spells: [14, 4], kda_ratio: 10.0, kill_participation: 0.78, dpm: 920,
    rating: 95, queue_id: 420, participants: null,
    lp_change: null, tilt_level: null, impact_rating: null, notes: null, vod_review: null,
    ...overrides,
  }
}

const meta: Meta<typeof RecordsCard> = {
  title: 'Components/RecordsCard',
  component: RecordsCard,
  decorators: [(Story) => <div style={{ maxWidth: 320, background: '#0A0A0F', padding: 16 }}><Story /></div>],
}
export default meta
type Story = StoryObj<typeof RecordsCard>

export const Empty: Story = { args: { matches: [] } }

export const WithRecords: Story = {
  args: {
    matches: [
      makeMatch({ game_id: '1', kills: 15, deaths: 1, assists: 10, kda_ratio: 25, dpm: 1100, kill_participation: 0.85, rating: 97 }),
      makeMatch({ game_id: '2', kills: 8, deaths: 6, assists: 12, kda_ratio: 3.3, dpm: 620, kill_participation: 0.65, rating: 72 }),
      makeMatch({ game_id: '3', win: false, kills: 3, deaths: 8, assists: 4, kda_ratio: 0.88, dpm: 410, kill_participation: 0.45, rating: 25 }),
    ],
  },
}
