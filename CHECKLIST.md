# LoL Tracker — Centro de Mando

Migracion de **Streamlit monolitico** → **FastAPI (backend) + SPA moderna (frontend)**.

**Leyenda:** `[x]` hecho y verificado · `[ ]` pendiente

---

> **Cierre v1.1 (2026-08-27):** la v1.1 esta completa. Backend solido (timing-safe auth,
> rate limiting 100 req/min, Sentry condicional, tabla `sync_runs` de auditoria, migrations
> idempotentes, codegen OpenAPI automatico), CI/CD (Postgres efimero + pytest + backups
> semanales), QA (30 backend + 35 frontend + 1 E2E = 66 tests), y frontend pulido
> (accesibilidad teclado, Storybook, empty states, touch-friendly). El unico pendiente
> operativo es el despliegue formal (Docker/VPS).

---

## Completado (v1.0)

### Backend & Datos

#### Nucleo y sincronizacion
- [x] Configuracion de FastAPI y endpoints base
- [x] Conexion con Supabase (psycopg3, pool async, `sslmode=require`)
- [x] Migraciones versionadas en `backend/migrations/` (matches, timestamptz, user_settings, participants)
- [x] Motor de Sincronizacion con Riot API (Match history)
- [x] Reintentos con backoff + respeto de `Retry-After` + errores reportados en `SyncResult`
- [x] PUUID cacheado 24h (una resolucion por sync, no una por partida)
- [x] Sync multi-cola: `POST /api/sync?queues=420,400` trae Ranked Solo + Normal Draft
- [x] Filtro de cola en `GET /api/matches?queue=ranked|normal`
- [x] Guardado de metricas completas y los 10 participantes por partida en DB (JSONB)
- [x] Stats participant-level reales del Riot API: `totalDamageDealtToChampions`, `totalDamageTaken`, `goldEarned`, `visionScore`
- [x] Timestamps en UTC explicito, independientes de la maquina
- [x] Rate limiter propio: todas las llamadas reintentan leyendo `Retry-After` con `asyncio.sleep()` exacto (tope 120s) + backoff exponencial de respaldo
- [x] Data Dragon patch resuelto dinamicamente con cache 1h
- [x] La `RIOT_API_KEY` nunca sale del backend; auth opcional por header `X-API-Token`

#### Endpoints y analitica
- [x] `GET /api/stats/champions` — rendimiento agregado por campeon con DPM REAL
- [x] `GET /api/stats/lp-trend` — LP acumulado con SQL window function + parametro `?queue=`
- [x] `GET /api/stats/heatmap` — winrate por dia x bloque horario (4 bloques de 6h)
- [x] `GET /api/stats/summary` — metricas agregadas (KDA, CS/min, winrate)
- [x] `GET /api/config` / `PUT /api/config` — configuracion persistente
- [x] `PATCH /api/matches/{game_id}` — campos subjetivos (LP, tilt, impact, notes, VOD); toda lectura tolera los cinco a `None`
- [x] `GET /api/constitution/status` — motor de reglas anti-tilt contra la config persistida
- [x] **Filtro anti-remake**: <300s excluidos de stats agregadas; La Constitucion valora solo Solo/Duo >=5 min; scout tambien filtrado
- [x] **Auto-tracker de LP (League-V4)**: al cerrar sync con partidas nuevas captura LP Solo/Duo → `lp_snapshots` (migracion 005); delta neto escrito como `lp_change` de la ultima ranked sin review manual
- [x] `GET /health` (abierto) + alias autenticado `GET /api/health` — DB + validez Riot key + warnings
- [x] Hub de metadatos cacheado: `GET /api/metadata/champions|items|spells`, diccionarios limpios con TTL 1h

#### Observabilidad y operacion
- [x] `POST /api/sync` como BackgroundTask: responde 202 al instante; `GET /api/sync/status` expone idle/processing/success/error
- [x] `pg_dump` contra Supabase como backup real (`backend/scripts/backup_supabase.py`, manual)
- [x] Logging con trazabilidad: middleware genera `X-Request-ID` (UUID) por peticion, cabecera + TODA linea de log via `contextvars`
- [x] Metricas de latencia: `LatencyRegistry` en memoria; `GET /api/metrics` (autenticado) con count/errores/p50/p95/max
- [x] Constraint mono-proceso forzada: el lifespan falla el arranque si detecta `--workers/-w >1`

#### Tests y migracion de datos
- [x] Backend: 30 tests hermeticos + 6 de integracion contra Postgres efimero del CI
- [x] 11 partidas legacy migradas de SQLite a Supabase (`migrate_sqlite.py`)
- [x] 40 partidas (400 participantes) re-puntuados con `rescore_participants.py` contra Supabase

### Frontend & UX

#### Infraestructura
- [x] Setup Vite + React 19 + TypeScript strict + Tailwind CSS v4 + TanStack Query v5
- [x] Layout con sidebar (drawer + hamburguesa <1024px) y rutas code-splitteadas con `<Suspense>` bajo el nav
- [x] Theme consistente: `#0A0A0F` body, `#14141C` cards, `#1A1A24` panels, purple accent, dark-only
- [x] API client (axios) + hooks React Query para todos los endpoints
- [x] Data Dragon icon normalization (`championKey()` con mapa de excepciones)
- [x] Error boundary global alrededor del `<Outlet/>` con fallback "Algo salio mal" + Reintentar
- [x] HealthBanner: consulta `/api/health` con sondeo cada 60s
- [x] Auto-sync silencioso al abrir la app (una vez por sesion, sin toasts si no hay novedades)

#### Paginas
- [x] Dashboard (`/`) — Matches table + Form Check + Performance Notes + Records + Champions + LP Trend
- [x] Champion Pool (`/pool`) — iconos Data Dragon, winrate bar, KDA, CS/min, DPM real
- [x] La Constitucion (`/constitution`) — banner de veredicto, 4 reglas, stats bar, boton de panico
- [x] Horarios / Heatmap (`/heatmap`) — grid 7x4, colores por winrate, tooltips, mejor/peor horario
- [x] Configuracion (`/settings`) — Champion Pool (max 3) + OKRs (CS/min, max deaths)

#### Tabla y Match Accordion
- [x] Tabla de alto rendimiento (skeletons shimmer, empty/error state), filtros All/Ranked/Normal persistentes en localStorage
- [x] Boton de Sync con spinner, invalidacion automatica de cache; polling de `/api/sync/status` cada 2.5s
- [x] Queue labels y spell icons reales; DPM/KP reales desde participant data
- [x] Accordion Blue/Red con 10 participantes reales; empty state honesto "Legacy" cuando `participants` es NULL
- [x] Full Stats: 8 metricas con colores condicionales; ELO/Notes con `computeEloFactors()` (7 dimensiones)
- [x] Review post-game (LP, tilt 1-5, impact rating, notes, VOD toggle) con updates optimistas
- [x] Rating 0-100 calculado en backend con baselines por rol `_ROLE_PROFILES`

#### Graficos y deep-linking
- [x] LP Acumulado — Recharts AreaChart con gradiente dinamico verde/rojo y tooltip personalizado
- [x] Heatmap — grid CSS color-coded con leyenda y deteccion automatica de peak/fatiga
- [x] Deep-linking: `?queue=` sincronizado bidireccionalmente via `useSearchParams`

#### Hooks
- [x] `useMatches`, `useSyncMatches`, `useUpdateMatchReview`, `useLpTrend`, `useChampionStats`, `useHeatmapStats`, `useConstitution`, `useSettings`/`useUpdateSettings`, `useHealth`

### Infraestructura & QA

- [x] CI en GitHub Actions completo: job backend (Postgres efimero + migraciones + pytest) y job frontend (npm ci → oxlint → vitest → build)
- [x] Frontend testeado: vitest + 28 tests unitarios
- [x] Code-splitting real (~112kB gzip Dashboard), todas las paginas lazy
- [x] TypeScript strict limpio (`"strict": true`)
- [x] PWA instalable: vite-plugin-pwa 1.3.0
- [x] Honestidad de datos: NoteBar fake eliminado, `mock.ts` eliminado, Dashboard desmockeado al 100%
- [x] Limpieza de legado: `app.py` Streamlit → `legacy/streamlit/`
- [x] `.devcontainer` actualizado a FastAPI + React
- [x] Documentacion viva: CLAUDE.md actualizado; README con operacion mono-proceso y nota Windows
- [x] E2E Playwright del flujo critico: Sync 202 → polling → partidas visibles → expandir → Review → PATCH → toast

### Decisiones de diseno registradas

- ~~Pagina "Diario"~~ — descartada (2026-08-23): la reflexion vive en las reviews por partida
- ~~Sesion con limites rigidos diarios~~ — descartada (2026-08-23): el control de tilt vive en La Constitucion
- ~~Rating con modificadores subjetivos~~ — descartado (2026-08-21): el rating es 100% objetivo
- Vista Scout — backend probado y UI retirada (2026-08-24): queda intacto para cuando vuelva de verdad

### Verificado sano en auditorias

- `.env` NO versionado; `backups/` gitignored; CORS con origenes explicitos; todo salvo `/health` detras de `X-API-Token`
- Rate limiting y reintentos hacia Riot solidos; fallos por partida reportados en `SyncResult`, nunca tragados
- Arranque degradado con pool caido + `/health` diagnostico honesto
- Error boundary + Suspense por ruta; strict mode TS limpio

---

## Completado (v1.1)

### Backend & Operacion

- [x] **Timing-safe token**: `secrets.compare_digest` en `deps.require_token` para prevenir ataques de timing
- [x] **Codegen de tipos OpenAPI**: `scripts/export_openapi.py` genera `openapi.json`, `npx openapi-typescript` genera `schema.d.ts`, `client.ts` re-exporta desde `generated.ts` — cero drift manual
- [x] **Migration runner idempotente**: `python -m backend.scripts.migrate` registra aplicadas en `_schema_migrations`, transaccional con savepoints
- [x] **Historial de syncs**: tabla `sync_runs` (migracion 006, repository, actualizacion en background task) — append-only, `_SyncState` sigue para polling rapido
- [x] **Backup semanal**: `.github/workflows/backup.yml` — pg_dump semanal (domingos 03:00 UTC) + workflow_dispatch, artifacto con 14 dias de retencion
- [x] **Sentry**: `sentry-sdk[fastapi]` en backend (condicional a `SENTRY_DSN`), `@sentry/react` en frontend (condicional a `VITE_SENTRY_DSN`), integrado con ErrorBoundary existente
- [x] **Rate limiting en memoria**: 100 req/min por token o IP, middleware Starlette en `backend/app/ratelimit.py`, solo rutas `/api/*`
- [x] **CI en GitHub Actions**: `.github/workflows/ci.yml` con Postgres efimero + `python -m backend.scripts.migrate` + pytest (backend) y npm ci → lint → test → build (frontend)

### Frontend & QA

- [x] **Empty states**: todos los componentes muestran estado vacio honesto con Lucide icons (sin emojis)
- [x] **Grid adaptativo**: breakpoints `sm`/`2xl` + overflow-x en HeatmapPage mobile
- [x] **Touch-friendly**: targets >=44px en nav, filtros, accordions, botones de accion
- [x] **Testing Library**: 35 tests frontend (28 unitarios + 7 render) con `@testing-library/react`
- [x] **Storybook**: componentes UI (ChampionsList, RecordsCard) con dark theme + backgrounds addon
- [x] **Accesibilidad teclado**: filas expandibles con `role="button"`, `tabIndex={0}`, `onKeyDown` para Enter/Space

---

## Pendiente (Backlog / Features futuras)

### Despliegue

- [ ] **Despliegue formalizado**: no hay Dockerfile/compose/fly.toml/render.yaml — hoy vive solo en la maquina local. Contenerizar backend+frontend y definir destino (VPS con `APP_API_TOKEN`, ya soportado) antes de usarlo fuera de casa

### Features futuras (sin fecha)

- [ ] Medallas/Badges automaticas por partida: CS God (CS/min >= 9), Muralla (deaths <= 2 + win), Feeder (deaths >= 7), Visionary (vision score >= 50), Carry (DPM >= 700 + win)
- [ ] Badges acumulativos: "Streak Master" (3+ wins seguidas), "Pool Purist" (100% partidas en pool champion)
- [ ] Badges visibles tanto en el accordion como en la tabla, y globales en el perfil resumen del Dashboard
- [ ] Exportar datos a CSV/JSON para analisis externo
- [ ] Comparacion con estadisticas globales de la ladder (challenger-v4 para percentiles; League-V4 ya integrado para LP)
- [ ] Notificaciones push cuando el sync detecta una racha de derrotas
- [ ] Multi-usuario: auth con Supabase Auth, dashboard compartido
- [ ] Integracion con overlay de OBS para streamers

### Deuda tecnica

- [ ] Eliminar `apply_migration_005.py` (one-off cuya migracion ya esta aplicada)

### Ideas de Brainstorming (Sin priorizar)

Ideas para v1.2 / v2.0. Mantienen la esencia: herramienta analitica seria y minimalista
para mejorar en League of Legends. Ninguna es social/gamificada por naturaleza.

#### Analitica y Estadisticas Avanzadas

1. **Tempo de Juego (oro al minuto 15)** — El predictor individual mas fiable de resultado.
   Riot Timeline (match v5) da snapshots de oro en intervalos regulares. Un grafico que
   cruce "tu oro al min 15 vs. winrate" por campeon revela donde realmente estas ganando
   o perdiendo: no es lo mismo llegar 1.5k ahead con Jinx que con Caitlyn. Implementacion:
   `/api/stats/tempo` consume timeline por partida, cachea el gold_diff@15 en participants
   JSONB y alimenta un Recharts AreaChart con percentiles por rol.

2. **Matriz de Matchups Personales** — Heatmap de tu winrate contra campeones especificos
   de la pool enemiga. "Jinx 60% general, pero 30% cuando el enemigo juega Caitlyn" es la
   clase de insight que cambia draft decisions. Datos ya estan en participants (enemy_champion
   + win); falta una query pivot con GROUP BY champion vs. enemy_champion y un grid
   coloreado tipo "champion select helper".

3. **Delta de Vision** — Vision score actual es un numero crudo que no dice nada. Un delta
   (tu vision score menos el del support enemigo en tu linea) indica si de verdad controlas
   visibilidad o solo pones wards que se limpian. Requiere el participant data del enemigo
   (ya lo tenemos en JSONB) y un calculo simple de diferencia por partida. Un trend line
   de delta de vision vs. winrate mostraria la correlacion real.

#### Vistas y Experiencia de Usuario

4. **Reporte Semanal ("Resumen de Semana")** — Pagina estatica tipo "Spotify Wrapped" que
   se genera cada lunes: partidas jugadas, winrate de la semana, delta de LP, campeones
   top/bottom, score de disciplina (La Constitucion), y un "momento de la semana" (mejor
   partida por rating). No es una notificacion: es una pagina que se abre y se consume en
   30 segundos. El hook seria un endpoint `GET /api/stats/weekly?weeks_back=1` que agrupa
   por rango de fechas.

5. **KPIs de Mejora (Trend Lines)** — Metricas especificas trackeadas en el tiempo con
   sparklines: "tu CS/min subio de 7.2 a 8.1 en las ultimas 30 partidas", "tu DPM bajo
   de 620 a 580 desde el parche X". Cada KPI tiene un trend arrow y un mini-grafico.
   Implementacion: una tabla `kpi_snapshots` que se actualiza al final de cada sync con
   metricas clave (cs_min, dpm, kda, vision_delta, deaths_avg) y un endpoint que devuelva
   la serie temporal. Esto responde a la pregunta "me estoy mejorando?" que ningun stat
   site responde.

6. **Analisis de Sesiones** — Agrupar partidas en "sesiones" (juego consecutivo con <30min
   de descanso entre ellos). Patron de tilt visible: "cuando pierdes la primera de una
   sesion, ganas solo el 25% de las siguientes". Implementacion: algoritmo de clustering
   por timestamp en el backend, endpoint `GET /api/stats/sessions` que devuelva sesiones
   con winrate, rating promedio y duracion. Un grafico de barras por sesion mostraria
   el patron de tilt de forma objetiva.

#### Backend, Seguridad e Integraciones

7. **Webhook de Discord** — Simple y pasivo: al completar un sync, enviar un embed a un
   canal de Discord con el resumen (partidas, W/L, LP delta, mejor rating). Configurable
   via `DISCORD_WEBHOOK_URL` en .env. Implementacion: 3 lineas en `_run_sync` al final
   del background task, httpx POST al webhook URL. No es notificacion push: es un log
   externo que te da visibilidad sin abrir la app.

8. **Alerta de Parche** — Cuando Data Dragon detecta un patch nuevo (el cache de 1h ya
   lo resuelve), comparar las stats de tus campeones de pool pre/post parche. Si un
   campeon recibio nerf significativo (Data Dragon no tiene notas de parche, pero el
   matchup matrix mostraria drop de winrate post-parche), mostrar un banner informativo
   en el Dashboard: "Patch 14.2 detectado: 2 campeones de tu pool afectados". Implementacion:
   comparar `dd_version` almacenado vs. actual; si cambia, re-evaluar winrate de pool en
   las ultimas N partidas vs. historico.
