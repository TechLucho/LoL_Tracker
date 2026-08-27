import { test, expect, type Page } from '@playwright/test'

// ── Mock data ──────────────────────────────────────────────────────────────────

const MOCK_MATCH = {
  game_id: 'EUW1_9999999001',
  date: '2026-08-27T14:30:00Z',
  champion: 'Ahri',
  role: 'MID',
  kills: 8,
  deaths: 3,
  assists: 12,
  cs_total: 187,
  cs_min: 7.2,
  control_wards: 2,
  win: true,
  enemy_champion: 'Yasuo',
  game_duration_minutes: 28.5,
  queue_id: 420,
  participants: [
    {
      champion_name: 'Ahri',
      puuid: 'test-puuid-1',
      player_name: 'TestPlayer#EUW',
      kills: 8, deaths: 3, assists: 12,
      cs: 187,
      items: [3089, 3157, 3165, 3020, 3152, 0, 3340],
      summoner_spells: [14, 4],
      team_id: 100, team_position: 'MID',
      win: true,
      total_damage: 24500, total_damage_taken: 12000,
      gold_earned: 11200, vision_score: 32,
      kill_participation: 0.72, rating: 78, rating_version: 1,
    },
  ],
  lp_change: null, tilt_level: null, impact_rating: null, notes: null, vod_review: null,
}

const MOCK_MATCH_AFTER_REVIEW = {
  ...MOCK_MATCH,
  lp_change: 21, tilt_level: 2,
  impact_rating: 'Hice mi trabajo',
  notes: 'Buena partida, controle midlane',
  vod_review: false,
}

// ── Test ───────────────────────────────────────────────────────────────────────

test.describe('Critical flow: Sync → Matches → Review', () => {
  test('syncs data, shows matches, and saves a review', async ({ page }) => {
    // Track how many times POST /api/sync fires (auto-sync = 1st, manual = 2nd)
    let postCount = 0
    let pollCount = 0

    // ── Static API mocks ──
    await page.route('**/api/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', database: true, riot_key_present: true, riot_key_type: 'production', warnings: [], uptime_seconds: 120 }) }),
    )
    await page.route('**/api/config', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ champion_pool: [], target_cs_min: 7.5, max_deaths: 5, updated_at: null, impact_ratings: [], regions: ['EUW1'], champion_pool_max: 3, display_timezone: 'Europe/Madrid', riot_id: 'Test', riot_region: 'EUW1' }) }),
    )
    await page.route('**/api/constitution/status', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', rules: [], verdict: 'green' }) }),
    )
    await page.route('**/api/metadata/champions', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ patch: '15.16.1', champions: {} }) }),
    )
    await page.route('**/api/metadata/items', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ patch: '15.16.1', items: {} }) }),
    )
    await page.route('**/api/metadata/spells', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ patch: '15.16.1', spells: {} }) }),
    )
    await page.route('**/api/stats/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    )

    // ── Matches: empty initially ──
    await page.route('**/api/matches**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    )

    // ── Sync mock (single handler for both auto-sync and manual sync) ──
    await page.route('**/api/sync**', async (route) => {
      const method = route.request().method()
      if (method === 'POST') {
        postCount++
        pollCount = 0
        return route.fulfill({
          status: 202, contentType: 'application/json',
          body: JSON.stringify({ status: 'processing', message: 'Sync started' }),
        })
      }
      // GET /api/sync/status
      pollCount++
      if (pollCount <= 1) {
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ status: 'processing', started_at: new Date().toISOString(), finished_at: null, result: null, error: null }),
        })
      }
      // First sync: 0 inserted. Second sync: 1 inserted.
      const inserted = postCount >= 2 ? 1 : 0
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          started_at: new Date().toISOString(),
          finished_at: new Date().toISOString(),
          result: { fetched: inserted, inserted, skipped: 0, errors: [] },
          error: null,
        }),
      })
    })

    // ── Navigate — auto-sync fires on mount ──
    await page.goto('/#/')

    // Wait for auto-sync to resolve (empty matches → "No matches found")
    await expect(page.getByText('No matches found')).toBeVisible({ timeout: 15_000 })

    // ── Now switch matches route to return data + register PATCH mock ──
    let patchReceived = false
    await page.route('**/api/matches**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_MATCH]) }),
    )
    await page.route('**/api/matches/EUW1_9999999001', async (route) => {
      if (route.request().method() === 'PATCH') {
        patchReceived = true
        const body = route.request().postDataJSON()
        expect(body.lp_change).toBe(21)
        expect(body.tilt_level).toBe(1)
        expect(body.impact_rating).toBe('Hice mi trabajo')
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(MOCK_MATCH_AFTER_REVIEW),
        })
      }
      return route.fallback()
    })

    // ── Click Sync ──
    await page.getByRole('button', { name: 'Sync', exact: true }).click()

    // ── Wait for match to appear ──
    await expect(page.getByText('Ahri')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('VICTORY')).toBeVisible()
    await expect(page.getByText('8/3/12')).toBeVisible()

    // ── Expand match → Review tab ──
    await page.getByText('Ahri').first().click()
    await page.getByRole('button', { name: /Review/ }).click()

    // ── Fill review form ──
    await page.getByPlaceholder('ej: +21 o -15').fill('21')
    await page.getByRole('button', { name: /Calma/ }).click()
    await page.getByRole('button', { name: /Hice mi trabajo/ }).click()
    await page.getByPlaceholder('¿Qué aprendí?').fill('Buena partida, controle midlane')

    // ── Save review ──
    await page.getByRole('button', { name: 'Guardar Review' }).click()

    // ── Verify PATCH + toast ──
    await expect.poll(() => patchReceived, { timeout: 5_000 }).toBe(true)
    await expect(page.getByText('Review guardada')).toBeVisible({ timeout: 5_000 })
  })
})
