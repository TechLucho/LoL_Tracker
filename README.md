# LoL Performance Tracker

Single-user, high-performance dashboard for League of Legends ranked discipline.
Built on **FastAPI** (backend) + **React 19 SPA** (frontend), backed by **Supabase PostgreSQL**.

> The application UI is in Spanish for personal use; codebase and documentation are in English.

## Features

- **Match history sync** from the Riot API (incremental, resumable, rate-limit-safe)
- **Performance analytics**: champion stats, session fatigue, LP trend, heatmap, trends, weekly reports
- **Scout**: Champion Mastery lookup for lane opponents directly in the match accordion
- **Tilt Alert**: losing-streak warning (3+ ranked losses) via Discord and in-app toast
- **Champion pool tracking** with per-role benchmarks (CS/min, DPM, KP%, vision)
- **Matchup notes** (persistent, per-matchup) and meta-verdict overlay

## Quick start

```bash
# Backend (Python 3.13, uvicorn) — `--reload-exclude` evita que tocar DBs (*.db/*.sqlite) reinicie el dev server
python -m uvicorn backend.app.main:app --reload --reload-exclude "*.db" --reload-exclude "*.sqlite"   # http://localhost:8000

# Frontend (Node >= 20, Vite)
cd frontend && npm install && npm run dev          # http://localhost:5173
```

See `.env.example` for required environment variables (Riot API key, Supabase DB credentials).

## Docs

- `AGENTS.md` — repository layout, commands, conventions
- `DESIGN.md` — frontend design system (tokens, components, palette)
- `CHECKLIST.md` — feature checklist and roadmap
