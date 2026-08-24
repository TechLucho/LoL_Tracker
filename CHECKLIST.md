# 🎯 LoL Tracker — Centro de Mando

Migración de **Streamlit monolítico** → **FastAPI (backend) + SPA moderna (frontend)**.

**Leyenda:** `[x]` hecho y verificado · `[ ]` pendiente · 🔴 bloqueador · ⚠️ deuda técnica que arrastramos

---

> **Estado (2026-08-23):** P0–P3 completados; **Sprint final (automatización) hecho**: hub de metadatos
> cacheado consumido por toda la UI, error boundary global, banner de salud, filtro anti-remake,
> CI en GitHub Actions, **auto-tracker de LP vía League-V4** (la gráfica de LP se alimenta sola)
> y **auto-sync silencioso al abrir la app**. Descartado por decisión de diseño: el concepto de
> "Sesión" (límites rígidos diarios), la página "Diario" y la página "Scout" — app más ligera y
> menos restrictiva (5 páginas). Backend con 36 tests (30 herméticos + 6 de integración sobre
> un Postgres efímero en CI): sync multi-cola en BackgroundTasks (POST 202 +
> GET /api/sync/status), pool de conexiones psycopg3, rating universal por participante calculado
> en backend con baselines por rol, participantes completos en JSONB, La Constitución, heatmap por
> bloques, LP trend acumulado. Frontend code-splitteado con datos 100% reales de Supabase,
> gráficos Recharts, configuración persistente y review post-game.
> **El MVP core y la capa de disciplina son 100% funcionales. La gamificación queda para un futuro sprint.**

---

## 1. Backend — Completado ✅

- [x] Configuración de FastAPI y endpoints base
- [x] Conexión con Supabase (psycopg3, pool async, `sslmode=require`)
- [x] Migraciones versionadas en `backend/migrations/` (matches, timestamptz, user_settings, participants)
- [x] Motor de Sincronización con Riot API (Match history)
- [x] Guardado de métricas completas y de los 10 participantes por partida en DB (JSONB)
- [x] Extraer participant-level stats reales del Riot API: `totalDamageDealtToChampions`, `totalDamageTaken`, `goldEarned`, `visionScore`
- [x] Sync multi-cola: `POST /api/sync?queues=420,400` trae Ranked Solo + Normal Draft
- [x] Filtro de cola en `GET /api/matches?queue=ranked|normal` (WHERE con queue_ids)
- [x] Reintentos con backoff + respeto de `Retry-After` + errores reportados en `SyncResult`
- [x] PUUID cacheado 24h (una resolución por sync, no una por partida)
- [x] Timestamps en UTC explícito, independientes de la máquina
- [x] Data Dragon patch resuelto dinámicamente con cache 1h
- [x] La `RIOT_API_KEY` nunca sale del backend
- [x] Auth opcional por header `X-API-Token`
- [x] 30 tests herméticos pasando (La Constitución + contrato + observabilidad + rating universal con baselines por rol) + 6 de integración contra el Postgres efímero del CI (ver Auditoría 🔴)
- [x] 11 partidas legacy migradas de SQLite a Supabase
- [x] `GET /api/stats/champions` — rendimiento agregado por campeón con avg_dpm calculado
- [x] `GET /api/stats/lp-trend` — LP acumulado con SQL window function
- [x] **Auto-tracker de LP (League-V4)**: al cerrar un sync con partidas nuevas se captura el LP de Solo/Duo (`Summoner-V4 by-puuid` → `League-V4 entries by-summoner`) y se guarda en `lp_snapshots` (migración 005); el delta neto entre snapshots se escribe automáticamente como `lp_change` de la partida ranked más reciente sin review manual — la gráfica acumulada se llena sola, sin tipeo manual. Fallo de League-V4 ≠ sync fallido (sólo se registra).
- [x] `GET /api/stats/heatmap` — winrate por día × bloque horario (4 bloques de 6h)
- [x] `GET /api/stats/summary` — métricas agregadas (KDA, CS/min, winrate)
- [x] `GET /api/config` / `PUT /api/config` — configuración persistente del usuario
- [x] `PATCH /api/matches/{game_id}` — actualización de campos subjetivos (LP, tilt, impact, notes, VOD)
- [x] `GET /api/constitution/status` — motor de reglas anti-tilt (racha, pool, muertes, farmeo)
- [x] **Filtro de remakes**: partidas < 300 s excluidas de las stats agregadas (`_NOT_A_REMAKE` en summary/champions/heatmap; lp-trend sin filtrar a propósito por ser review subjetivo)
- [x] `GET /health` (abierto) + alias autenticado `GET /api/health` — DB + validez de Riot key + warnings
- [x] **Hub de metadatos cacheado** (Data Dragon): `GET /api/metadata/champions|items|spells`, diccionarios limpios id → nombre/descripción/URL con TTL 1h en el backend

---

## 2. Frontend — MVP Core + P1: Completado ✅

### Infraestructura
- [x] Setup Vite + React + TypeScript + Tailwind CSS v4 + TanStack Query
- [x] Layout principal con sidebar sticky y 5 rutas navegables
- [x] Theme consistente: `#0A0A0F` body, `#14141C` cards, `#1A1A24` panels, purple accent
- [x] API client (axios) + hooks React Query para todos los endpoints
- [x] Data Dragon icon normalization (`championKey()` con mapa de excepciones)
- [x] **Error boundary global** (`react-error-boundary`) alrededor del `<Outlet/>` con fallback "Algo salió mal" + botón Reintentar; `resetKeys` lo resetea al navegar
- [x] **Banner de salud** (`HealthBanner.tsx`): consulta `/api/health` al cargar, banner ámbar/naranja fijo sobre el layout cuando hay avisos o el backend no responde
- [x] Tabla, accordion, Settings y Champions consumen `/api/metadata/*` — cero URLs de Data Dragon hardcodeadas en componentes (quedan sólo como fallback mientras cargan los metadatos)
- [x] **Auto-sync silencioso al abrir**: el `Layout` dispara `useSyncMatches({ silent: true })` una vez por sesión; sin toasts si no hay partidas nuevas (sólo avisa si trae datos frescos); errores cubiertos por el HealthBanner

### Tabla de Partidas (`/`)
- [x] Tabla de alto rendimiento (skeletons, empty state, error state)
- [x] Filtros funcionales (All Matches, Ranked, Normal)
- [x] Botón de Sync con spinner, invalidación automática de caché
- [x] Queue labels: "Ranked Solo", "Normal Draft"
- [x] Spell icons reales (mapping ID → Data Dragon)
- [x] DPM real y Kill participation real calculados del participant data

### Match Accordion (desplegable)
- [x] Blue/Red Side con 10 participantes reales de Supabase
- [x] Avatares, items (6 slots), hechizos, KDA, CS de cada participante
- [x] Pestaña Full Stats: 8 métricas reales con colores condicionales
- [x] Pestaña ELO/Notes: `computeEloFactors()` analiza 7 dimensiones, calcula net impact
- [x] Pestaña Review: form post-game (LP, tilt 1-5, impact rating, notes, VOD toggle)
- [x] Rating score (0-100) calculado en el backend con baselines por rol (KDA, CS/min, KP, DPM, visión, muertes, win/loss) con fallback local en el cliente

### Páginas
- [x] **Dashboard** (`/`) — Matches table + Form Check + Performance Notes + Records + Champions + LP Trend
- ~~[x] **Diario** (`/diario`)~~ — **DESCARTADO (2026-08-23)** por decisión de diseño: ruta, entrada del nav y componente eliminados. Comparte causa con el descarte de "Sesión": app más ligera, menos restrictiva
- ~~[x] **Scout** (`/scout`)~~ — **RETIRADO (2026-08-24)**: ruta y entrada del nav eliminadas; el backend (`/api/scout/*`) queda intacto y probado para cuando la UI vuelva de verdad
- [x] **Champion Pool** (`/pool`) — tabla con iconos Data Dragon, winrate bar, KDA, CS/min, DPM
- [x] **La Constitución** (`/constitution`) — banner de veredicto, 4 reglas, stats bar, botón de pánico
- [x] **Horarios / Heatmap** (`/heatmap`) — grid 7×4 día×bloque, colores por winrate, tooltips, mejor/peor horario
- [x] **Configuración** (`/settings`) — Champion Pool (max 3) + OKRs (CS/min, max deaths)

### Gráficos
- [x] **LP Acumulado** — Recharts AreaChart con gradiente dinámico (verde/rojo), tooltip personalizado
- [x] **Heatmap** — grid CSS con winrate color-coded, leyenda, detección automática de peak/fatiga

### Hooks y Datos
- [x] `useMatches()` — query + mapBackendToUI con datos reales
- [x] `useSyncMatches()` — mutation POST 202 + polling de `/api/sync/status` cada 2.5s + cache invalidation
- [x] `useUpdateMatchReview()` — mutation PATCH para review post-game
- [x] `useLpTrend()` — query para gráfico LP acumulado
- [x] `useChampionStats()` — query para tabla de campeones
- [x] `useHeatmapStats()` — query para heatmap
- [x] `useConstitution()` — query para reglas anti-tilt
- [x] `useSettings()` / `useUpdateSettings()` — query + mutation para configuración

---

## 3. P2 — Polish & Gamificación 🟡 Polish ✅ · Gamificación pendiente

### Visual Polish
- [x] Rediseño visual de la pestaña "Match": alineación correcta de avatares, items y summoner spells en el accordion de participantes
- [x] Mejorar el layout del accordion: spacing consistente entre columnas, items alineados en grid, spells con labels tooltip
- [ ] Estados vacíos con ilustraciones/emojis más expresivos en cada página
- [x] Skeleton loaders más elaborados ( shimmer effect en vez de pulse uniforme )
- [x] Transiciones de entrada suaves en las páginas (fade-in)

### Gamificación y Feedback
- ~~Sesión con límites rígidos diarios (máx. partidas/día, tracking de sesión)~~ — **DESCARTADO (2026-08-23):** decisión de mantener la aplicación más ligera y menos restrictiva; el control de tilt vive en La Constitución (reglas suaves), no en límites duros
- [ ] Medallas/Badges automáticas por partida: 🌾 CS God (CS/min ≥ 9), 🧱 Muralla (deaths ≤ 2 + win), 🤡 Feeder (deaths ≥ 7), 👁️ Visionary (vision score ≥ 50), 🔥 Carry (DPM ≥ 700 + win)
- [ ] Badges acumulativos: "Streak Master" (3+ wins seguidas), "Pool Purist" (100% partidas en pool champion)
- [ ] Badges visibles tanto en el accordion de la partida como en la tabla de historial
- [ ] Badges globales en el perfil resumen del Dashboard

### Rating y Métricas
- [x] Refinar baselines del cálculo de Rating por rol (Top vs Support) — `_ROLE_PROFILES` en `services/riot.py`: CS/min target 7.5 lanes / 5.75 jungla / 1.25 soporte, KP con peso x30 y visión/min para jungla y soporte, DPM target por rol
- ~~Rating factor: bonus por horario pico / fidelidad al pool / penalización por tilt~~ — **DESCARTADO (2026-08-21):** decisión de mantener el Rating 100% objetivo, sin modificadores de disciplina

### UX Interactions
- [x] Updates optimistas al guardar review (el UI se actualiza antes de la respuesta del servidor) → **hecho (2026-08-24)**: `onMutate` cancela refetches, parchea todas las cachés `['matches']` y guarda snapshot; `onError` revierte en silencio + toast; `onSettled` resincroniza siempre
- [x] Deep-linking de filtros: `?queue=` en la URL sincronizado bidireccionalmente (la URL manda sobre localStorage) → **hecho (2026-08-24)**; parámetros por página (p. ej. `#/pool?champion=Jax`) siguen en backlog
- [x] Confirmación visual al guardar review (toast notification)
- [x] Filtros persistentes en localStorage

---

## 4. Auditoría integral (2026-08-23) 🔍

Revisión línea a línea de los archivos críticos tras cerrar el sprint de automatización.
Verificado en verde: `riotwatcher 3.3.1` soporta `summoner.by_puuid` + `league.by_summoner`
(el auto-tracker LP funciona); pool/main.py/db.py sólidos; CI, metadatos y sync en background OK.

### Datos falsos o inconsistentes (prioritario — el proyecto es anti-mentira)
- [x] 🔴 **NoteBar es fake de punta a punta**: hace `PATCH /matches/EUW_LATEST` (id inexistente → 404 siempre) y el `catch` muestra check verde de "guardado". Decidir: columna `next_game_note` en `user_settings` (+ GET/PUT ya existentes) o eliminar el componente → **eliminado** (componente borrado)
- [x] 🟠 **PLACEHOLDER_PLAYERS en MatchAccordion**: si `participants` es NULL se renderizan 10 jugadores inventados ("Lucho#EUW", stats de fantasía). Sustituir por empty state honesto ("Partida anterior al esquema de participantes") → **hecho**, empty state "Datos detallados no disponibles para esta partida (Legacy)"
- [x] 🟠 **DPM estimado en `/api/stats/champions`**: `champion_performance()` aún usa la fórmula legacy `(K·450 + A·250 + CS·min·3.2)/duración`; el daño REAL está en `participants->>'total_damage'` (JSONB). El accordion muestra DPM real pero ChampionsList/Champion Pool muestran el estimado → calcular AVG sobre el JSONB → **hecho**, `avg_dpm` = AVG del daño real del JSONB (participante localizado por campeón; filas sin participants/duración no contaminan)
- [x] 🟠 **Scout sin filtro anti-remake**: `nemesis()` y `search_matchups()` no aplican `_NOT_A_REMAKE` → remakes <5 min contaminan los winrates de rivales y matchups → **hecho**, ambas queries aplican `_NOT_A_REMAKE`
- [x] 🟠 **La Constitución cuenta remakes**: `matches.last_results()` no filtra duración ni cola → un remake perdido puede disparar el STOP obligatorio. Aplicar `game_duration_minutes >= 5` (y valorar sólo Solo/Duo) → **hecho**, `last_results()` filtra `>= 5 min AND queue_id = 420` y `/api/constitution/status` comparte la misma ventana
- [x] 🟡 **Dashboard semi-mockeado**: FormCheckCard (12 métricas), PerformanceNotes (8 "insights" — BO3/BO5 no existen en solo queue: reescribir), RecordsCard (6 récords) y ChampionsList vienen de `mock.ts`. Los 4 son computables con datos ya sincronizados → **hecho**: todo se calcula sobre partidas sincronizadas reales vía `data/insights.ts` — ChampionsList usa `useChampionStats()` (winrate/KDA/DPM real del backend), FormCheck compara últimas 5 vs 5 anteriores, Records calcula récords del historial, PerformanceNotes muestra racha previa (2W/2L) y franjas horarias con muestra suficiente; BO3/BO5 eliminados

### Pulido menor detectado
- [x] `lp_trend` mezcla todas las colas: las normals entran como 0 LP y diluyen la gráfica — añadir parámetro `queue=420` (el auto-tracker sólo asigna LP a ranked) → **hecho**, backend acepta `?queue=` y `useLpTrend` pide siempre 420
- [x] `useHealth` sin `refetchInterval`: el HealthBanner no se actualiza si el backend cae/reviva a mitad de sesión (~60s de refetch) → **hecho**, sondeo cada 60s; el banner desaparece solo al revivir el backend
- [x] `mock.ts` tiene exports muertos (`MATCHES`, `RATING_TREND`) y aloja interfaces que deberían vivir en `types.ts` → migrar tipos y borrar el resto → **hecho**, archivo eliminado; interfaces útiles (`FormCheckMetric`, `RecordEntry`, nueva `InsightNote`) migradas a `types.ts`
- [x] Paginación de historial ausente en UI: `getMatches(limit=50)` trunca silenciosamente; añadir "Cargar más" (backend ya pagina con limit/offset) → **hecho**, `useMatches` migrada a `useInfiniteQuery` (páginas de 50) con botón "Cargar más" en la tabla
- [ ] `apply_migration_005.py` era one-off: eliminar (la migración ya está aplicada)
- [x] CLAUDE.md decía "24 passing" ×2 — corregido a la cifra real (27)

---

## 5. P3 — Deuda Técnica & Futuro ⚠️

### Responsive / Mobile
- [x] Sidebar colapsable en móvil: drawer deslizante + hamburguesa en header propio <1024px; cierra al navegar, con backdrop y Escape (`inert` evita tabular dentro del menú oculto) → **hecho (2026-08-24)**
- [ ] Grid adaptativo restante del "responsive completo" (la tabla ya scrollea y las columnas xl apilan; queda revisar densidades intermedias)
- [ ] Touch-friendly: botones más grandes, swipe en accordion
- [x] PWA: manifest + service worker para uso offline del dashboard cacheado → **hecho (2026-08-24)** vía vite-plugin-pwa (ver Auditoría 🟠); probar con `npm run build && npm run preview` (el SW no se activa en `npm run dev`)

### Backend / Infra
- [ ] Re-puntuar participantes ya sincronizados: `insert_many` usa `ON CONFLICT DO NOTHING`, así que las filas existentes conservan el rating de la fórmula plana; hace falta un script one-off que recalcule `rating` en el JSONB con `_ROLE_PROFILES` (sin tocar los campos de review subjetivos) — **script listo** (`backend/scripts/rescore_participants.py`, idempotente y con `rating_version`); pendiente solo de ejecutarlo contra Supabase
- [x] `pg_dump` contra Supabase como backup real (`backend/scripts/backup_supabase.py`, manual; requiere `pg_dump` en PATH)
- [x] `POST /api/sync` como `BackgroundTask` + endpoint de progreso (evitar timeout en syncs grandes) — POST responde 202 al instante; `GET /api/sync/status` expone idle/processing/success/error y el frontend hace polling cada 2.5s
- [x] Tests de repositorios contra una DB real (no solo contrato Pydantic) → **hecho (2026-08-24)**: `backend/tests/integration/` contra el Postgres efímero del CI; en local se auto-saltan sin `TEST_DATABASE_URL`
- [x] Endpoint de metadatos de campeones cacheado (evitar fetch de Data Dragon en cada carga) — ampliado a hub completo: `/api/metadata/champions|items|spells` + CI en GitHub Actions (pytest, tsc, oxlint)
- [x] Rate limiter propio: evitar 429 de Riot más allá del BasicRateLimiter de riotwatcher — todas las llamadas (cuenta, matchlist, partida) reintentan leyendo `Retry-After` con `asyncio.sleep()` exacto (tope 120s) y backoff exponencial de respaldo
- [x] Observabilidad: logging estructurado + métricas de latencia por endpoint → **hecho (2026-08-24)**: `X-Request-ID` por petición en cabecera y logs (contextvars), `GET /api/metrics` con p50/p95/max en memoria (ver Auditoría 🟠). Verificado en vivo con uvicorn real: el id de la cabecera coincide con las líneas de log de esa petición. Hallazgo extra: en Windows, `uvicorn` SIN `--reload` usa ProactorEventLoop y psycopg async no conecta — ahora hay warning accionable en el arranque y nota en README

### Frontend / DX
- [x] Code-splitting: lazy load de páginas para reducir bundle inicial (< 500kB)
- [ ] Tests E2E con Playwright para los flujos críticos (sync → review → constitution)
- [x] TypeScript strict mode: resolver todos los `any` implícitos → **hecho**, `"strict": true` en `tsconfig.app.json` y `tsconfig.node.json`; build 100% limpia sin tocar código (ya estaba tipada)
- [ ] Storybook para componentes UI (MatchAccordion, HeatmapGrid, WinrateBar)

### Limpieza de Legado
- [x] `scripts/test_api.py` — roto (método inexistente + API key hardcodeada): corregir o eliminar
- [x] `scripts/` — migrar a `scripts/legacy/` o eliminar los que ya no aplican (movidos a `legacy/streamlit/scripts/`)
- [x] `app.py` (Streamlit legacy) — mover a `legacy/streamlit/` como referencia histórica
- [x] `.devcontainer/devcontainer.json` — actualizar para apuntar a FastAPI + React (puertos 8000/5173, Node 22, postgresql-client, deps instaladas en postCreate)
- [x] `CLAUDE.md` — actualizar con la nueva arquitectura (FastAPI + React)
- [x] Limpiar `__pycache__/` sueltos del repo   

### Features Futuras (Backlog)
- [ ] Exportar datos a CSV/JSON para análisis externo
- [ ] Comparación con estadísticas globales de la ladder (Riot API) — League-V4 ya integrado para LP; ampliar a challenger-v4 para percentiles
- [ ] Notificaciones push cuando el sync detecta una racha de derrotas
- [ ] Multi-usuario: auth con Supabase Auth, dashboard compartido
- [ ] Integración con overlay de OBS para streamers
- [x] Dar datos reales a la sección "Champions" — iconos vía Hub de Metadatos; conectar `useChampionStats()` (pendiente, ver Auditoría)
- [ ] Revisar las secciones "Form Check" y "Performance Notes" (confirmado mockeadas, ver Auditoría) → **hecho en Prioridad 2**: ambas calculan sobre datos reales vía `data/insights.ts`
- [x] Vista "Scout" — desarrollada (nemesis + matchups); queda el filtro anti-remake (ver Auditoría)

---

## 5. Auditoría Final v1.0 (Deuda Técnica y Pulido Nivel Producción) 🔍

> Auditoría Staff Engineer post-MVP (2026-08-24), tras cerrar Sprint C. Verificada contra el código
> real (no contra intenciones): CI, tests, logging, hooks de React, layouts CSS y `index.html`.
> Ordenada por prioridad dentro de cada pilar. El MVP es funcional y honesto en sus datos; esta
> lista es lo que separa "funciona en mi máquina" de "aplicación de producción".

### 🔴 Crítico — socava la confianza o bloquea iterar con seguridad

- [x] **Tests de integración backend contra Postgres efímero**: los 27 tests herméticos son contratos OpenAPI + lógica pura (Constitución, Rating). → **hecho (2026-08-24)**: servicio `postgres:16` en el workflow + migraciones `backend/migrations/*.sql` aplicadas en orden antes de pytest; `conftest.py` detecta `CI=true` y apunta al efímero (`DB_SSLMODE=disable`, el servicio no lleva TLS); nueva carpeta `backend/tests/integration/` que se auto-salta sin `TEST_DATABASE_URL` en local. Cubiertas las queries señaladas: `insert_many` idempotente, anti-remake de `list_recent`, ventana Solo/Duo ≥5min de `last_results`, DPM real por JSONB de `champion_performance`, acumulado+filtro de cola en `lp_trend` y exclusiones de `nemesis`. Sin cubrir aún: heatmap, paginación fina y `search_matchups`
- [x] **Frontend sin ni un test** (`package.json` no tiene script `test`; sin vitest/playwright): la lógica pura recién extraída a `data/insights.ts` (`computeFormCheck`, `computeRecords`, `computePerformanceNotes`) y los fallbacks legacy de `mapBackendToUI` (DPM/KP/rating estimados) son perfectamente testeables hoy mismo y sostienen todo el Dashboard "100% real". Mínimo viable: vitest + Testing Library para insights/types; Playwright después para E2E.
  → **Hecho (2026-08-24)**: vitest 4 instalado, script `npm run test`, 25 tests unitarios verdes — `insights.test.ts` cubre FormCheck/Records/Notes (dirección lowerIsBetter, umbral ±2%, franjas horarias, omisión de cubos vacíos) y `useMatches.test.ts` cubre los fallbacks legacy (DPM/KP/rating estimados vs dato real del backend que SIEMPRE gana). Config en `vite.config.ts` (environment node); paso "Tests unitarios" añadido al job de frontend en CI. Pendiente: Testing Library para componentes.
- [ ] **E2E del flujo crítico Sync → Review → Constitución** (ya estaba en backlog): mockear Riot a nivel de red (Playwright `page.route` / MSW) y verificar: sync 202→polling→partidas visibles, guardar review persiste LP/tilt/notas, STOP obligatorio aparece tras 2 derrotas.
- [x] **Scout: backend completo, frontend muerto** — `/api/scout/nemesis` y `/api/scout/matchups` existen, están testeados y tienen anti-remake, pero `ScoutPage.tsx` son dos tarjetas "Próximamente". O se conecta (hooks + UI de tarjetas/buscador) o se retira la ruta del nav; un ítem de navegación vacío es exactamente el tipo de fachada que este proyecto prohíbe.
  → **Decisión (2026-08-24): retirar**. Eliminados `ScoutPage.tsx`, la ruta en `App.tsx` y el ítem del nav en `Layout.tsx` (verificado: build/lint/tests verdes). El backend scout queda intacto y probado para cuando la UI vuelva.

### 🟠 Importante — experiencia y operativa degradadas

- [x] **Tabla de partidas rota en móvil**: `ROW_GRID` suma ~710px mínimos en 9 columnas y el contenedor NO tiene `overflow-x-auto` (el accordion de participantes sí). En <768px se recorta/aplasta. → **hecho (2026-08-24)**: filas y skeletons envueltos en `overflow-x-auto` (scroll horizontal sin aplastar columnas), "Cargar más" movido fuera del scroller para permanecer centrado, y el sidebar ya es drawer con hamburguesa <1024px (ver Responsive/Mobile en P3)
- [x] **Optimistic updates al guardar Review**: `useUpdateMatchReview()` espera round-trip completo antes de invalidar `['matches']`. Con `onMutate` (cache set tentativo + snapshot para rollback) la UI responde instantáneo y revierte con toast si falla. → **hecho (2026-08-24)**: exactamente ese patrón implementado
- [x] **Deep-linking de estado**: HashRouter da rutas compartibles (#/constitution), pero el filtro de cola vive SÓLO en `localStorage` (`lol_tracker.queue_filter`) y `expandedId` del accordion es estado local. Sincronizar con search-params para que compartir URL preserve la vista. → **hecho (2026-08-24)**: `?queue=` sincronizado bidireccionalmente vía `useSearchParams` (`replace: true`, sin ensuciar el historial); la URL manda sobre localStorage si trae valor válido, localStorage queda como fallback. `expandedId` sigue siendo estado local a propósito (es UI efímera, no contexto compartible)
- [x] **Logging estructurado + trazabilidad**: había `logging` estándar bien usado (sync en background hace `log.exception`, LP capturado avisa sin romper el sync ✅) pero texto plano sin request-ID ni duraciones. → **hecho (2026-08-24)**: middleware HTTP genera `X-Request-ID` (UUID) por petición, lo devuelve como cabecera y lo inyecta en TODA línea de log vía `contextvars` + filtro en el handler raíz (`observability.py`) — incluidos los logs del sync en background, que heredan el contexto al crearse. Formato: `ts LEVEL [request_id] logger: msg`. Uvicorn conserva sus handlers propios (propagate=False), sin colisión.
- [x] **Métricas básicas de latencia/errores**: no existía `/metrics`. → **hecho (2026-08-24)**: nivel mínimo elegido a propósito (sin Prometheus/APM externo): `LatencyRegistry` en memoria alimentada por el mismo middleware; `GET /api/metrics` (autenticado) expone count/errores/p50/p95/max por plantilla de ruta (`/api/matches/{game_id}`, no path literal — cero cardinalidad por id), ventana móvil de 500 muestras. Suficiente para VER un pico de Supabase; si algún día hay multi-proceso esto rompería junto con `_SyncState` (y el arranque lo impide).
- [x] **PWA instalable**: `index.html` no tenía manifest, theme-color ni service worker. Para una herramienta de uso entre partidas, instalable en móvil/desktop es alto valor bajo coste. → **hecho (2026-08-24)**: `vite-plugin-pwa` 1.3.0 en modo `generateSW` + `autoUpdate` (registro inyectado en index.html, sin tocar `main.tsx`); manifest "LoL Tracker"/"Tracker" con colores del tema (`#0A0A0F`/`#14141C`) e iconos placeholder 192/512 (glifo ⚔ sobre fondo oscuro) en `public/`; `theme-color` y viewport anti double-tap-zoom en el HTML; workbox precachea 27 entradas (~840 kB) con `navigateFallback: index.html`. Pendiente sólo el arte definitivo de los iconos
- [x] **CI incompleto**: no corría `npm run build` (vite build real). → **hecho (2026-08-24)**: job de frontend completo (`npm ci` → oxlint → vitest → build) y job de backend con Postgres efímero + migraciones + pytest (ver punto 🔴 anterior)
- [x] **Constraint mono-proceso no forzada**: `_SyncState` del sync vive en memoria — correcto a propósito, pero `uvicorn --workers 2` rompería silenciosamente el polling de `/status`. → **hecho (2026-08-24)**: el lifespan verifica `--workers/-w` en argv y `UVICORN_WORKERS`/`WEB_CONCURRENCY` en el entorno y FALLA el arranque con mensaje accionable si detecta multi-worker (falso negativo exótico < bloquear un arranque legítimo); documentado en README ("Running the server — SINGLE PROCESS ONLY", con Procfile) y CLAUDE.md. Escalar vertical, no horizontal.

### 🟡 Mejora futura — pulido nivel producción

- [ ] Comparación de token timing-safe: `deps.require_token` usa `!=`; cambiar a `secrets.compare_digest` (riesgo bajo en single-user, fix trivial).
- [ ] Codegen de tipos desde OpenAPI (`openapi-typescript`): hoy `client.ts` duplica a mano los esquemas Pydantic (`ChampionPerf`, `HealthStatus`…) — riesgo de drift silencioso ya ocurrido históricamente (KDA string vs número).
- [ ] Historial de syncs persistido: `_SyncState` sólo recuerda la última ejecución y se pierde al reiniciar; tabla `sync_runs` daría auditoría de fallos de Riot.
- [ ] Backup automático: `backup_supabase.py` existe pero es manual; programar (GitHub Action semanal con secret, o cron) + retención.
- [ ] Migration runner idempotente: las migraciones se aplican a mano en orden; un `python -m backend.scripts.migrate` que registre las aplicadas eliminaría el error humano.
- [ ] Accesibilidad teclado/táctil: las filas expandibles de la tabla son `<div onClick>` sin `role="button"`/`tabIndex`/manejo de Enter/Space.
- [ ] Despliegue formalizado: no hay Dockerfile/compose/fly.toml/render.yaml — hoy vive en la máquina local. Contenerizar backend+frontend y definir destino (VPS con `APP_API_TOKEN`, ya soportado) antes de usarlo fuera de casa.
- [ ] Error tracking frontend/backend (Sentry/GlitchTip self-hosted): el ErrorBoundary de `Layout.tsx` evita la pantalla blanca pero nadie se entera de que ocurrió.
- [ ] Tests de carga/limiting propios de la API: sin rate-limit por token (mono-usuario, prioridad baja real).

### ✅ Verificado sano durante la auditoría

- `.env` NO versionado (gitignored, confirmado con `git ls-files`); `backups/` ignorado.
- CORS con orígenes explícitos; `/health` abierto a propósito y el resto detrás de `X-API-Token`.
- Rate limiting y reintentos hacia Riot sólidos (Retry-After + backoff, techos definidos); fallos por partida reportados en `SyncResult`, nunca tragados.
- Arranque degradado con pool caído + `/health` diagnóstico (sin falso positivo de dev key desde Prioridad 1).
- Error boundary + Suspense por ruta; code-splitting real (~112kB gzip Dashboard); strict mode TS limpio.
