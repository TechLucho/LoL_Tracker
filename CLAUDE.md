# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-user dashboard for League of Legends ranked discipline. It is **not** a stat site: the point
is the human layer on top of the stats — tilt management ("La Constitución" stop-loss rules), a
strictly enforced champion pool, an objective per-game rating, and finding the hours of the week where
the user actually wins.

**Architecture: FastAPI backend + React SPA frontend.** The original Streamlit monolith is dead and
archived under `legacy/streamlit/` — historical reference only. Never import from it, never
reintroduce `sqlite3`, never resurrect `app.py`/`database.py`/`riot_client.py` at the root.

## Repo layout

```
backend/
  app/
    main.py          # FastAPI app, lifespan (pool open/close), CORS, router wiring
    config.py        # pydantic-settings; validates ALL env vars at startup
    db.py            # psycopg3 AsyncConnectionPool (min 1 / max 5), sslmode=require
    deps.py          # require_token (X-API-Token header)
    schemas.py       # Pydantic models (Match, Participant, StatsSummary, ...)
    routers/         # matches, stats, scout, sync, config, constitution, health, metadata
    services/        # riot.py (sync + rating), datadragon.py, constitution.py
    repositories/    # SQL lives here: matches, stats, scout, settings, lp
  migrations/        # versioned SQL applied manually (001…005)
  scripts/           # migrate_sqlite.py (legacy ETL), backup_supabase.py (pg_dump)
  tests/             # pytest: 30 hermetic + integration/ (ephemeral Postgres in CI)
frontend/
  src/
    pages/           # 6 pages, all React.lazy code-split
    components/      # MatchesTable, MatchAccordion, Layout, PageLoader, ...
    hooks/           # TanStack Query wrappers (useMatches, useSyncMatches, ...)
    api/client.ts    # axios instance
legacy/streamlit/    # DEAD monolith (app.py, database.py, riot_client.py, old scripts)
data/                # lol_tracker.db = legacy SQLite, already migrated to Supabase
```

## Commands

On this Windows machine the `python` on PATH is the Microsoft Store stub, which fails. Use the real
interpreter:

```powershell
$PY = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"

# Backend (from repo root) — API on http://localhost:8000, docs at /docs
& $PY -m pip install -r backend/requirements.txt
& $PY -m uvicorn backend.app.main:app --reload

# Frontend (from frontend/) — dev server on http://localhost:5173
npm install
npm run dev          # vite
npm run build        # tsc -b && vite build
npm run lint         # oxlint

# Tests (from repo root) — 30 hermetic tests, no DB needed (contract + observability + rules engine).
# tests/integration/ needs TEST_DATABASE_URL (ephemeral Postgres; applied by CI, skipped otherwise)
& $PY -m pytest backend/tests -q

# Backup (from repo root) — requires pg_dump on PATH; writes backups/backup_<timestamp>.sql
& $PY -m backend.scripts.backup_supabase
```

Scripts under `backend/scripts/` must run as modules (`python -m backend.scripts.…`) from the repo
root — plain paths break imports because Python puts the script's own directory on `sys.path`.

There is no formatter configured; frontend linting is `oxlint`.

## Configuration
 
Everything comes from `.env` at the repo root via pydantic-settings (`backend/app/config.py`). See
`.env.example` for the authoritative template. An incomplete `.env` **prevents the backend from
booting** — that is by design (the Streamlit monolith used to degrade silently to "no data").

| Variable | Purpose |
| --- | --- |
| `RIOT_API_KEY` | Riot key. Dev keys (`RGAPI-…`) expire every 24h; `/health` reports when one is a dev key. |
| `RIOT_ID` | Default Riot ID, `Name#TAG`. |
| `RIOT_REGION` | Platform id (`EUW1`, `LA1`, …). Validated against `ROUTING_MAP` in `config.py`. |
| `DB_HOST` `DB_NAME` `DB_USER` `DB_PASSWORD` `DB_PORT` | Supabase Postgres (pooler host). `DB_USER` must be `postgres.<project-ref>`. |
| `DISPLAY_TIMEZONE` | Zone used to interpret heatmap hours. Defaults to `Europe/Madrid`. |
| `APP_API_TOKEN` | If set, all endpoints except `/health` require `X-API-Token`. Empty = open (local use). |
| `CORS_ORIGINS` | JSON array. Defaults to the Vite dev server origins. |

## Backend behavior worth knowing

- **Connection pool**: opened once in the FastAPI lifespan, reused by every request. This replaces
  the monolith's ~10 TCP+TLS handshakes per click. If the pool fails at startup the process still
  boots in degraded mode so `/health` can explain what's wrong — check `/health` first when panels
  look empty.
- **Single-process by design**: sync state (`_SyncState`) and latency metrics live in process
  memory. Startup fails fast if `--workers > 1`, `UVICORN_WORKERS` or `WEB_CONCURRENCY` > 1 —
  scale vertically, never into multiple worker processes.
- **Observability middleware**: every request gets a `X-Request-ID` (also embedded in every log
  line via a `contextvars` filter, background tasks included) and feeds p50/p95/max latency stats
  exposed at `GET /api/metrics` (auth-required).
- **Windows event loop**: async psycopg needs a selector loop; on Windows, uvicorn only forces one
  under `--reload`. A bare run boots degraded with a startup warning — keep `--reload` locally,
  deploy to Linux/Docker.
- **Schema is migration-managed**, not created at runtime. Apply SQL files from `backend/migrations/`
  manually, in order. There is no ORM; repositories write raw SQL with psycopg3.
- **Timestamps are stored in UTC**; `DISPLAY_TIMEZONE` only affects how heatmap hours are grouped for
  display. Don't mix local-time assumptions into queries.
- **Auth**: `deps.require_token` guards everything except `/health`.
- **Sync** (`POST /api/sync?queues=420,400`): resolves the Riot ID → PUUID once per sync (cached 24h),
  then fetches match details per match. Retries use exponential backoff and respect `Retry-After`;
  failures are reported per-match in `SyncResult` instead of being swallowed.
- **Data Dragon patch** is resolved dynamically (1h cache) — there is no hardcoded patch string
  anywhere. `GET /api/datadragon/version` exposes it.

## Data layer

Supabase PostgreSQL. Tables: `matches` (one row per game), `user_settings` (champion pool, OKRs),
plus participant data stored as **JSONB inside `matches`** (see `004_participants.sql`).

- Each participant carries: `puuid`, `player_name` (`GameName#TAG`), champion, position, KDA, cs,
  `items` (7 slots, index 6 = trinket), `total_damage`, `kill_participation`, `vision_score`,
  `gold_earned`, `rating`.
- **The 0–100 rating is computed in the backend** (`calculate_participant_rating` in
  `services/riot.py`) from objective inputs only: win/loss, KDA, CS/min, KP, DPM, deaths. Decision
  (2026-08-21): the formula stays 100% objective — **no discipline modifiers** (no tilt penalty, no
  pool-fidelity bonus). The frontend has a `computeRating()` fallback for rows synced before the
  field existed; backend value wins whenever present.
- Subjective review fields (`lp_change`, `tilt_level`, `impact_rating`, `notes`, `vod_review`) are
  nullable and updated via `PATCH /api/matches/{game_id}`. Every read path must tolerate `None`
  (a synced-but-unreviewed match has all five unset).
- Analytics live in SQL (window functions for LP trend, `EXTRACT(DOW)` grouping for the heatmap,
  aggregate queries for champions/summary) — not in pandas.

## Frontend notes

- Stack: React 19, TypeScript, Vite 8, Tailwind CSS **v4**, TanStack Query v5, axios, Recharts,
  react-router-dom v7 (**HashRouter**), sonner (toasts), lucide-react (icons).
- **Tailwind v4 is CSS-first**: design tokens and custom animations live in `frontend/src/index.css`
  (`@theme`, `@keyframes`). There is **no `tailwind.config.js`** — don't create one.
- All 6 pages are `React.lazy()`-loaded; the `<Suspense>` lives in `Layout.tsx` around the `<Outlet>`
  so the sidebar stays visible while a chunk loads. The content wrapper is keyed by pathname to
  replay the fade-in on every navigation.
- Theme: body `#0A0A0F`, cards `#14141C`, panels `#1A1A24`, purple accent. Dark-only.
- The queue filter persists in `localStorage` under `lol_tracker.queue_filter`; review saves confirm
  via sonner toast ("✅ Review guardada").
- UI strings are Spanish; identifiers and DB columns are English. Emoji in UI labels is intentional.

## Legacy & data safety

- `legacy/streamlit/` exists only as historical reference. `data/lol_tracker.db` (11 matches,
  2025-12-25 → 2026-01-10) was migrated to Supabase via `backend/scripts/migrate_sqlite.py`
  (`export` → `import` → `verify`); keep both until certain, but never wire them into the app again.
- Real backups mean `pg_dump` against Supabase (`backend/scripts/backup_supabase.py` → `backups/`,
  gitignored). Copying SQLite files backs up nothing current.
