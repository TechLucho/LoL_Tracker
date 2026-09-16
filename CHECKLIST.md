# LoL Tracker — Centro de Mando

Migracion de **Streamlit monolitico** → **FastAPI (backend) + SPA moderna (frontend)**.

**Leyenda:** `[x]` hecho y verificado · `[ ]` pendiente

---

> **Cierre v2.2 (2026-09-16):** Auditoría, rediseño global y estabilización. Ejecutada "La Gran Purga" eliminando más de 1,000 líneas de código muerto (vistas `/pool`, `/constitution` y endpoints huérfanos). Rediseño completo del frontend aplicando el nuevo `DESIGN.md` (tipografía mono-eyebrow, botones pill neón, tarjetas surface-1). Fixes críticos resueltos: error 500 en Trends por casteo numérico en Postgres y error 500 en Scout por el nuevo nivel de maestría sin tope de Riot. QA en verde (71 pytest + 40 vitest). Todo listo para iniciar el Sprint 1 del multijugador (El Rosco).

---

> **Cierre v2.1 — Onboarding y sesión (2026-09-13):** Riot ID vinculado por usuario y primer
> flujo de arranque real. **P0:** `user_settings` gana `riot_id`/`riot_region` (migración 014,
> aplicada a la DB de Supabase) y todo el pipeline lee del `CurrentUserId` — `/api/sync`, la
> captura de LP y `RiotService` ya no tocan el `RIOT_ID` del `.env`; `_SyncState` es por
> `user_id` y el `409` de sync en curso solo bloquea al mismo usuario. **P1:** endpoint
> `PUT /api/settings/riot` (valida formato `Nombre#TAG` y región contra `ROUTING_MAP`),
> onboarding `RiotOnboarding.tsx` con el guard `RequireLinked` (sin `riot_id` el Dashboard
> queda oculto y solo se ve el formulario; al vincular se monta el Layout y el auto-sync
> inicial arranca solo) e interceptor 401 global en el client axios (`signOut` local +
> `queryClient.clear()` + toast "Sesión expirada" + redirect a `/login` conservando la ruta
> previa; los 401 simultáneos se colapsan en uno). QA en verde: **91 pytest + 40 vitest +
> oxlint + build** (commits `e2ab253` y `a2fc6d8`). Pendiente para cerrar la v2.1: panel de
> configuración para re-vincular Riot ID/región desde `/settings`.

---

> **Cierre v2.0 (2026-09-12):** cierre de la migración SaaS multi-tenant tras la auditoría
> técnica completa. Auth delegado 100% a **Supabase Auth**: registro/login en la SPA, tokens de
> sesión JWT verificados en el backend por algoritmo dinámico — HS256 con `SUPABASE_JWT_SECRET`
> o ES256/RS256 contra la JWKS pública (`PyJWKClient` + `cryptography`, caché por URL y fetch
> fuera del event loop vía `asyncio.to_thread`). Datos aislados por usuario: migración 013
> (`user_id` en todas las tablas transaccionales + RLS `auth.uid() = user_id`) y toda query de
> repos condicionada por el `user_id` del JWT. Frontend con `AuthContext` + interceptor Bearer,
> página de Login y guard de rutas. Liquidadas las deudas de la auditoría: rate limiter sin
> `X-API-Token`, contrato OpenAPI regenerado (HTTPBearer), auth v1 archivada en
> `legacy/auth_v1/`, React Query sin reintentos en 4xx (429-safe), fixes SQL de stats
> (parámetros de timezone y `ORDER BY` de agregados). QA en verde: **85 pytest + 40 vitest +
> oxlint + build**. Queda fuera de cierre (roadmap v2.1): el sync aún usa el `RIOT_ID` global del
> `.env` y `_SyncState` es compartido — vincular el Riot ID por usuario y separar el estado del
> sync son las dos primeras piezas pendientes.

---

> **Cierre v1.6 (2026-09-12):** Analítica de sesión, validación de OKRs, Escout de rivales en caché, Sync reanudable y Baselines comparativas de Élite.

---

> **Cierre v1.3 (2026-09-11):** cierre oficial de la v1.3 tras auditoría técnica completa
> (Postgres/JSONB, seguridad, resiliencia del sync, React Query, bundle) con QA en verde:
> 37 pytest + 35 vitest + oxlint + build. La v1.3 añade sobre la v1.2: Heatmap con umbrales
> (mejor/peor franja con mínimo de 3 partidas), Analítica de Laning (Timeline de Riot →
> GD@15/XPD@15/CSD@15 y RadarChart en Tendencias), Delta de Visión (tendencia vs. rival de
> línea), Dispersión KP% vs. winrate, Alerta de Parche dinámica (banner en Dashboard), nuevos
> OKRs configurables (DPM, KP%, Vision Score) en Settings, y Alerta de racha de derrotas
> (Tilt Alert: 3+ derrotas → Discord en rojo + toast en la app). Pendientes no bloqueantes:
> aplicar migraciones 008 y 009 en Supabase (validadas en CI) y el despliegue formal (sigue
> abierto en la v1.1).

---

> **Cierre v1.2 (2026-08-28):** la v1.2 introduce la capa de analítica avanzada. Implementada la
> vista de Matchups (con notas persistentes en DB), agrupación por sesiones lógicas en el
> Dashboard, KPIs de tendencia (CS/min, DPM, KDA), Reporte Semanal estático y notificaciones
> pasivas por Discord.

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
- [x] La `RIOT_API_KEY` y las credenciales de DB nunca salen del backend; auth por sesión Supabase (JWT HS256/ES256 vía JWKS) en `Authorization: Bearer`

#### Endpoints y analitica
- [x] `GET /api/stats/champions` — rendimiento agregado por campeon con DPM REAL
- [x] `GET /api/stats/lp-trend` — LP acumulado con SQL window function + parametro `?queue=`
- [x] `GET /api/stats/heatmap` — winrate por dia x bloque horario (4 bloques de 6h)
- [x] ~~`GET /api/stats/summary`~~ — eliminado en purga v2.1 (endpoints y schemas huérfanos)
- [x] `GET /api/config` / `PUT /api/config` — configuracion persistente
- [x] `PATCH /api/matches/{game_id}` — campos subjetivos (LP, tilt, impact, notes, VOD); toda lectura tolera los cinco a `None`
- [x] ~~`GET /api/constitution/status`~~ — eliminado en la fase de poda (views + backend constitution)
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
- [x] ~~Champion Pool (`/pool`)~~ — eliminado en la fase de poda; widget `ChampionsList` en Dashboard
- [x] ~~La Constitucion (`/constitution`)~~ — eliminado en la fase de poda (views + backend constitution)
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
- [x] `useMatches`, `useSyncMatches`, `useUpdateMatchReview`, `useLpTrend`, `useChampionStats`, `useHeatmapStats`, ~~`useConstitution`~~, `useSettings`/`useUpdateSettings`, `useHealth`

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

- `.env` NO versionado; `backups/` gitignored; CORS con origenes explicitos; todo salvo `/health` detras de `get_current_user` (JWT Supabase, HS256/ES256 vía JWKS)
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

## Completado (v1.3)

### Analítica avanzada y nuevas vistas

- [x] **Vista de Matchups (con notas persistentes en DB)**: stats históricas del cruce Tú vs. campeón enemigo (`GET /api/stats/matchups/{user}/{enemy}`) + notas persistentes por emparejamiento (`/api/matchup-notes`, tabla propia vía migración), página `/matchups`
- [x] **Análisis de sesiones (agrupación visual por días)**: el Dashboard agrupa la lista plana de partidas en bloques diarios con su balance de victorias/derrotas ("5V - 2D") sobre el "Logical Gaming Day" (offset nocturno) e ignorando los remakes; cada bloque abre con un separador "Hoy"/"Ayer"/fecha amigable
- [x] **KPIs de mejora (Trend lines)**: endpoint `GET /api/stats/trends` que devuelve la serie temporal (cs_min, dpm real, kda) de las últimas 50 partidas válidas, y página `/trends` con tres gráficas de línea apiladas (Recharts) en el tema oscuro con tooltip personalizado
- [x] **Reporte Semanal**: endpoint `GET /api/stats/weekly` (7 días según fecha UTC: partidas, winrate, KDA medio con tolerancia a nulos, top campeón y mejor partida por rating) y página `/weekly` con tarjetas visuales grandes, avatares de Data Dragon y estado vacío amigable

### Limpieza e integraciones

- [x] Eliminado `backend/scripts/apply_migration_005.py` (deuda técnica; las migraciones ya las cubre el runner idempotente)
- [x] **Webhook de Discord**: `DISCORD_WEBHOOK_URL` en config; al cerrar `_run_sync` (éxito o error) se envía un embed de resumen (estado final + partidas añadidas) vía httpx, silenciando cualquier error de red

### Nuevas características (2026-09-11)

- [x] **Triángulo del Laning (Timeline)**: el sync pide `/matches/{match_id}/timeline` por partida ≥15 min, toma el frame más cercano a 900.000 ms y guarda `gd15`/`xpd15`/`csd15` (tus stats − rival con mismo `teamPosition`) en el JSONB del participante; `GET /api/stats/laning` promedia las últimas 50 válidas y Tendencias las pinta en un RadarChart normalizado (0.5 = duelo parejo). Fallos del timeline = warning + partida intacta, nunca tumba el sync
- [x] **Delta de Visión**: `TrendPoint.vision_delta` (tu `vision_score` − el del rival directo de línea) extraído con `JOIN LATERAL` en `kpi_trend`; gráfica de tendencia en `/trends`
- [x] **Dispersión KP% vs. Winrate**: componente de dispersión cruzando Kill Participation con victorias para definir tu estilo de juego (splitpush vs teamfight)
- [x] **Alerta de Parche dinámica**: `game_version` por partida (migración 008); winrate del pool en el parche actual vs. histórico (`GET /api/stats/patch-alert`, caída >4pp con mínimo 5 partidas del parche actual → banner en Dashboard). Parche resuelto de Data Dragon sin hardcodeo
- [x] **Heatmap con umbrales**: mejor/peor franja sólo cuando hay ≥3 partidas en la franja (`_MIN_GAMES_FOR_BEST_WORST`); sin muestra suficiente, `best_slot`/`worst_slot` son null
- [x] **Nuevos OKRs configurables**: `target_dpm`, `target_kp_percent`, `target_vision_score` en `user_settings` (migración 009) y formulario en Settings con validación de rangos
- [x] **Alerta de racha de derrotas (Tilt Alert)**: `SyncResult.losing_streak_warning` cuando las últimas 3+ partidas Ranked válidas son derrotas; embed de Discord en rojo y toast en la app (se dispara también en el auto-sync)

---

### Deuda técnica de auditoría (v1.3.1)

- [x] Reintentar errores de red puros (timeout/conexión) en `_call_with_retry` — hoy solo se captura `ApiError`; un `status=None` debería ser `retryable=True`
- [x] No fijar `_state.status = "processing"` hasta obtener `run_id` (si `start_run` falla, el sync queda bloqueado en 409 hasta reiniciar)
- [x] Eliminar el motor de La Constitución duplicado (`/api/stats/constitution` + `services/constitution.py`, muertos) y cubrir el rules-engine activo (`/api/constitution/status`) con tests herméticos
- [x] `insert_many` en lote (executemany / VALUES multi-fila) en vez de 1 INSERT por partida
- [x] Aplicar migraciones 008 y 009 en Supabase (validadas en CI; sin 009 el PUT de config falla)
- [x] Version string de `main.py` ("2.0.0-dev") y `backend/README.md` (documenta el endpoint de Constitution muerto) al día

---

## Completado (v1.6)

> Cierre oficial 2026-09-12 (v1.4 → v1.6): analítica de sesión, validación de OKRs, escout de
> rivales en caché, sync reanudable y baselines comparativas de élite. QA en verde: 75 pytest
> + 40 vitest + oxlint + build. Auditoría final con parche del race del guard 409 y deuda de
> tooling liquidada (Storybook/Chromatic/Playwright).

### Medio plazo

- [x] **Resumen por rol / campeón de la semana**: winrate y KDA por (campeón, rol, cola) con mínimo de partidas para sacar conclusiones honestas ("solo rindes con Jax en toplane") — `GET /api/stats/champion-summary` (HAVING ≥ 3) + tarjeta `ChampionRoleSummary` en Dashboard
- [x] **Carga acumulada de sesión**: winrate de las últimas 5 partidas vs. las 5 anteriores, para detectar el punto donde entras en autopilot (apoya la agrupación por sesiones del Dashboard) — `GET /api/stats/session-fatigue` + banner `SessionFatigueCard` (caída ≥20pp de winrate o −2.0 KDA)
- [x] **Objetivos por partida vía OKRs**: marcar en la review si cumpliste DPM/KP%/Visión — conecta los OKRs de Settings con el resultado real de la partida — strip `🎯 OKR` en el accordion de cada partida (check/cruz contra `target_dpm`, `target_kp_percent`, `target_vision_score`)
- [x] **Escout del pool rival**: winrate del champion pool del rival de línea por rol, integrado en la vista Matchups — v1 implementada como **Champion Mastery**: `GET /api/matches/{game_id}/scout-opponent` devuelve los 3 campeones más jugados del rival de línea (OTP vs first time), cacheada 24h en `scout_cache` para no quemar la cuota de Riot, con tab 🔎 Escout en el accordion
- [x] **Veredicto de meta**: cruzar la matriz de matchups contra `game_version` para alertar cuándo tu pool pierde contra el meta del rango (extensión natural de la Alerta de Parche) — `GET /api/stats/meta-verdict` compara winrate por (tú vs enemigo) del parche actual contra el histórico y marca `meta_shift` (favorable ≥55% antes, <50% ahora) con toggle "Filtro de Meta Actual" en Matchups

### Fase 1 del largo plazo (v2.0)

- [x] **Sync reanudable**: checkpoint por partida + detección de "Riot degradado" para abortar esperas de backoff largas — micro-lotes de 5 partidas persisten al vuelo (`on_match` en `fetch_recent_matches`), `RiotDegradedError` aborta limpio (429 con Retry-After > 60s o 5xx agotados), estado `partial` con `degraded_api: true` y toast naranja de aviso en la UI
- [x] **Comparación con estadísticas globales de la ladder**: línea base por rol (CS/min, DPM, KP%, Visión) inyectada por participante en la serialización (`services/baselines.py`, espejo de `_ROLE_PROFILES` para no contradecir el rating) y renderizada en la vista Full Stats de cada partida — valor real destacado + `Exp: …` en gris con flecha verde ▲ si superas la base del rol; `GET /api/stats/baselines` expone el mapa completo

---

## Completado (v2.1)

> Archivado 2026-09-13 (P0 + P1 del roadmap de la auditoría v2.0 / onboarding): Riot ID por
> usuario, sync concurrente y manejo global de sesión expirada. QA en verde: 91 pytest + 40
> vitest + oxlint + build (commits `e2ab253` P0 y `a2fc6d8` P1).

- [x] **Migración multi-usuario y concurrencia**: `user_settings` gana `riot_id`/`riot_region`
  (migración 014, aplicada a Supabase) y el pipeline (sync, captura de LP, `RiotService`) lee
  del `CurrentUserId`, desacoplándolo del `RIOT_ID` global del `.env`; `_SyncState` pasa de
  global a dict por `user_id`, así el `409` de "sync en curso" solo bloquea al mismo usuario.
- [x] **Flujo de Onboarding (Wizard obligatorio)**: `PUT /api/settings/riot` (valida formato
  `Nombre#TAG` y región contra `ROUTING_MAP`) + `RiotOnboarding.tsx` a pantalla completa; el
  guard `RequireLinked` oculta el Dashboard hasta vincular y el auto-sync inicial arranca solo.
- [x] **Manejo de Sesión Expirada**: interceptor 401 global en el client axios →
  `supabase.auth.signOut()` (scope local, sin red) + `queryClient.clear()` + toast "Sesión
  expirada" + redirect a `/login` conservando la ruta previa; los 401 en ráfaga se colapsan.

---

## Completado (v2.2)

### Plan de Acción Inmediato (liquidado en esta versión)

- [x] **Fase 0: Auditoría Completa y Poda Extrema.** Eliminadas las vistas muertas `/pool` y
      `/constitution`, el motor duplicado de La Constitución (`services/constitution.py`,
      `GET /api/stats/constitution`) y las rutas huérfanas de `router/api.py` en la purga
      v1.1. En la purga v2.2 se eliminaron más tipos/schemas y endpoints y se regeneró el
      contrato OpenAPI (commits `bab12ad`, `d8b756d`).
- [x] **Fase 1: UI Core - Estilizar Onboarding y Configuración (Cierre v2.1).** Aplicadas las
      nuevas reglas del `DESIGN.md` a `RiotOnboarding.tsx` (botones pill con neón, tarjetas
      `surface-1`, bordes `hairline`, tipografía monoespaciada) y refactorizada la vista
      `/settings` integrando la re-vinculación del Riot ID y el indicador de `/health`
      (commit `7861fab`).
- [x] **Heredado de v2.1 — Panel de configuración completo** — re-vincular Riot ID/región
      desde la UI (hoy también en el onboarding), estado de conexión (`/health`) con indicador
      en Settings y verificación de email en el flujo de registro.

### Fixes de backend

- [x] **Fix Trends 500 — ROUND(double precision):** `kpi_trend` en `repositories/stats.py`
      dividía `numeric / float8` (daño real / duración) para calcular DPM y luego pasaba el
      resultado a `ROUND()`. Postgres no admite `ROUND(double precision, integer)` — solo
      `ROUND(numeric, integer)`. Solución: cast explícito del resultado de la división a
      `::numeric` antes de redondear. Endpoint `GET /api/stats/trends` restaurado a 200.
- [x] **Fix Scout 500 — mastery_level sin tope:** Riot eliminó el cap de nivel 7 en Champion
      Mastery en 2026 — `championLevel` ahora es un entero sin tope (1.2M pts ≈ lvl 113). El
      schema Pydantic lo validaba con `le=7`, rechazando toda respuesta de Riot. Solución:
      eliminar `le=7` (queda `ge=0`), regenerar contrato OpenAPI y añadir lectura tolerante de
      caché (`try/except ValidationError`) para payloads de schemas anteriores. Endpoint
      `GET /api/matches/{game_id}/scout-opponent` restaurado a 200.

---

## Pendiente (Backlog / Features futuras)

### Despliegue

- [ ] **Despliegue formalizado**: no hay Dockerfile/compose/fly.toml/render.yaml — hoy vive solo en la maquina local. Contenerizar backend+frontend antes de usarlo fuera de casa

### Roadmap v2.3 — Multijugador: El Rosco

> **Concepto:** minijuego 1v1 en tiempo real construido sobre Supabase Realtime. Dos jugadores
> compiten en partidas privadas: se miden en minijuegos de trivia que otorgan segundos extra y
> cierran con **El Rosco**, la ronda alfabética que decide al ganador.

- **Objetivo:** minijuego 1v1 en tiempo real usando Supabase Realtime.
- **Flujo:** Lobby por código → Fase de Draft (elección de minijuegos) → Minijuegos (acumular segundos extras) → El Rosco final.

#### Reglas de Negocio (cerradas 2026-09-13 · casos límite resueltos)

1. **Autoridad (anti-trampas) y fuente de verdad** — Validación estricta en el **backend**, que
   es el **árbitro y dueño absoluto del estado**. El frontend envía cada respuesta al servidor
   (REST); el backend valida contra la pregunta oficial, calcula aciertos/fallos y emite el
   broadcast por **Realtime**. El estado vivo de la partida (letras pendientes, tiempo restante,
   turno actual) vive en **memoria en FastAPI** (`dict[room_code, GameState]`); el frontend es
   "tonto": solo envía acciones y pinta la UI según los eventos del servidor. La DB
   (`game_rooms`) persiste el emparejamiento y el resultado final, **no** el estado en vivo.
   Los broadcasts del cliente nunca son de confianza.
2. **Turnos del Rosco (múltiples vueltas)** — Clásico "a la contra" con **múltiples vueltas**
   como en el programa real. Un jugador arranca en la **A**; si acierta, avanza a la siguiente
   letra; si **falla o dice "pasapalabra"**, la letra queda en estado **pendiente** (o
   **fallada**), su reloj se congela y cede el turno al rival, que arranca donde este se quedó.
   Al completar la vuelta (Z), su siguiente turno retoma la **primera letra pendiente** e itera
   hasta agotar su tiempo o responder todas las letras.
3. **Economía y Reloj** — Banco de tiempo **estrictamente individual**: cada jugador arranca con
   un banco base de **100 segundos** al que se suman exclusivamente los segundos que **él mismo**
   acumuló en los minijuegos. El reloj es un **contador continuo** (recurso estratégico): decrece
   en tiempo real mientras sea tu turno; un **acierto no lo detiene** y pasas automáticamente a
   la siguiente letra; solo se congela ante **fallo** o **pasapalabra**. Quien gane los
   minijuegos gana el derecho a empezar el Rosco. Si el tiempo llega a **0**, termina el turno de
   ese jugador.
4. **Empates (tiebreaker)** — 1º gana quien tenga **más letras acertadas**; 2º a igualdad de
   letras, **quien conserve más tiempo restante**; 3º si todo coincide, **empate**.
5. **Normalización extrema** — La validación convierte a **minúsculas**, elimina **tildes** y
   borra **todo carácter no alfanumérico** (espacios, apóstrofos, guiones): `"Nunu & Willump"`
   → `nunuwillump`, `"Kog'Maw"` → `kogmaw`. Un fallo tipográfico es fallo, no un "casi".
6. **Desconexiones** — Si **Presence** detecta la caída de un jugador, la **partida se pausa**
   (reloj detenido, sin procesar respuestas) con un **grace period estricto de 60 segundos**: si
   no se reconecta a tiempo, **pierde por abandono (forfeit)**. Si el host desaparece
   definitivamente, la sala se cierra y **expulsa al invitado**.
7. **Idioma del contenido** — Los datos se extraen de **Data Dragon con locale `es_ES`**: lore
   y nombres de habilidades en español oficial.
8. **Ordering del seed** — En el **Sprint 1** se crea una semilla mínima de prueba (**26
   preguntas, una por letra** del abecedario) para poder testear El Rosco en el **Sprint 4**;
   la integración masiva con Riot queda para el **Sprint 5**.

#### Restricciones Técnicas

- Sin matchmaking público por ahora: solo **salas privadas por código** de 6 letras.
- Todo el contenido (preguntas y categorías) se precarga en **PostgreSQL**; nada de consultas a Riot en plena partida.

#### Sprints de Implementación

- [x] **Sprint 1: Infraestructura y Lobby (REST).** Migración SQL para `game_rooms` (id, room_code, host, guest, status) y `rosco_questions`. Endpoints en FastAPI para crear sala y unirse por código de 6 letras. Normalizador de texto (regla 5) + **semilla mínima de 26 preguntas** (regla 8).
- [x] **Sprint 2: Conexión Realtime (Frontend).** UI del Lobby. Conexión de React al canal `room:{code}` de Supabase. Sincronización de presencia (Host avisa cuando entra el Guest) y **pausa por desconexión con grace period de 60s → forfeit** (regla 6).
- [x] **Sprint 3: Sistema de Draft y Minijuegos.** Máquina de estados en la DB (`lobby` -> `drafting` -> `minigames`). Sistema de selección de 2 categorías alternando turnos. Motor de conversión de puntos a segundos que alimenta el banco de tiempo (regla 3).
- [ ] **Sprint 4: El Rosco (Core Game).** Estado alfabético (A-Z, Pasapalabra, Acierto, Fallo) mediante broadcasts de Supabase con **validación estricta en backend y estado vivo en memoria** (`dict[room_code, GameState]`, regla 1). Turnos "a la contra" con múltiples vueltas (regla 2), banco individual de 100s y contador continuo (regla 3), tiebreaker de victoria/empate (regla 4) y normalización extrema (regla 5). Probado contra la semilla de 26 letras.
- [ ] **Sprint 5: Seed de Contenido (DataDragon).** Script Python que extrae campeones, habilidades, lore y fechas desde la API estática de Riot con locale `es_ES` (regla 7) e inyecta cientos de preguntas base en PostgreSQL.

### Ideas Congeladas (Prioridad Nula)

Ideas que alguna vez se consideraron pero que no aportan valor suficiente para justificar el
desarrollo. Se conservan aquí como referencia histórica por si el contexto cambia.

- **Medallas dinámicas**: "CS God", "Muralla", etc., calculadas de forma relativa a tu propio histórico (ej. mejor CS de tus últimas 50 partidas) en lugar de umbrales fijos.
- **Badges acumulativos**: "Streak Master" (3+ wins seguidas), "Pool Purist" (100% partidas en pool).
- **Badges visibles** en el accordion, tabla y perfil resumen del Dashboard.
- **Exportar datos a CSV/JSON** para análisis externo.
- **Integración con overlay de OBS** para streamers.
- **Reporte semanal a Discord**: cruce de `weekly_report` (ya implementado) con el webhook ya existente
