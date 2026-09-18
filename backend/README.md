# LoL Tracker — Backend

API REST en FastAPI que reemplaza al monolito Streamlit. Expone los datos de Supabase y de la API
de Riot al frontend, sin que ninguna credencial llegue al navegador.

## Arranque

```powershell
$PY = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"   # el `python` del PATH es el stub de Store

& $PY -m pip install -r backend/requirements.txt
& $PY -m uvicorn backend.app.main:app --reload --reload-exclude "*.db" --reload-exclude "*.sqlite"
```

Docs interactivas en <http://localhost:8000/docs>. Todos los comandos se ejecutan **desde la raíz
del repo**, no desde `backend/` (los imports son `backend.app.*`).

## Puesta en marcha por primera vez

1. `cp .env.example .env` y rellenar credenciales.
2. Aplicar migraciones **en orden** en el SQL Editor de Supabase:
   - `backend/migrations/001_matches.sql`
   - `backend/migrations/002_timestamptz.sql` ← requerida; revisa la zona asumida (Europe/Madrid)
3. Migrar el historial legacy:
   ```powershell
   & $PY -m backend.scripts.migrate_sqlite export   # ya hecho -> data/legacy_matches.json
   & $PY -m backend.scripts.migrate_sqlite import
   & $PY -m backend.scripts.migrate_sqlite verify
   ```
4. `GET /health` para confirmar conexión a DB y estado de la key de Riot.

## Estructura

| Carpeta | Responsabilidad |
| --- | --- |
| `app/config.py` | Env vars validadas al arrancar; `ROUTING_MAP` de regiones; DSN de libpq |
| `app/db.py` | Pool async único por proceso (`AsyncConnectionPool`) |
| `app/schemas.py` | Contrato de la API (Pydantic) |
| `app/repositories/` | Todo el SQL. Nada de SQL fuera de aquí |
| `app/services/` | Riot API y lógica de dominio (rating, datadragon) |
| `app/routers/` | Endpoints HTTP. Sin SQL ni reglas de negocio |
| `migrations/` | Esquema versionado, fuera del runtime |
| `scripts/` | Utilidades operativas (migración del SQLite legacy) |

## Endpoints

| Método | Ruta | Notas |
| --- | --- | --- |
| `GET` | `/health` | Sin auth. Diagnostica credenciales de DB y dev key caducada |
| `GET` | `/api/matches` | `?limit=&offset=` |
| `PATCH` | `/api/matches/{game_id}` | Campos subjetivos. `null` explícito **borra**; omitir **no toca** |
| `POST` | `/api/sync` | Devuelve `{fetched, inserted, skipped, errors[]}` |
| `GET` | `/api/stats/champions` | Incluye `winrate` y `kda_ratio` calculados en SQL |
| `GET` | `/api/stats/champion-summary` | Winrate/KDA por (campeón, rol, cola) con `HAVING` ≥ 3 partidas |
| `GET` | `/api/stats/session-fatigue` | Últimas 5 vs. anteriores 5: detecta autopilot (caída ≥20pp WR / −2 KDA) |
| `GET` | `/api/stats/heatmap` | Agrupado en `DISPLAY_TIMEZONE`, no en UTC ni en la tz del servidor |
| `GET` | `/api/stats/lp-trend` | LP acumulado; `has_lp` distingue "0" de "sin registrar" |
| `GET` | `/api/stats/trends` | Serie temporal de KPIs (CS/min, DPM, KDA, visión) |
| `GET` | `/api/stats/laning` | Triángulo del Laning: GD@15 / XPD@15 / CSD@15 promediados |
| `GET` | `/api/stats/patch-alert` | Caída de winrate del pool tras un parche de Data Dragon |
| `GET` | `/api/stats/weekly` | Resumen de la última semana (partidas, winrate, top campeón) |
| `GET` | `/api/stats/meta-verdict` | Winrate por (tú vs enemigo) del parche actual contra el histórico: marca `meta_shift` (favorable ≥55% antes, <50% ahora, mín. 3 partidas del parche) |
| `GET` | `/api/matches/{game_id}/scout-opponent` | 3 campeones más jugados del rival de línea (Champion Mastery de Riot), con caché 24h en `scout_cache` |

## Decisiones de diseño

**Sin `except` genéricos que oculten fallos.** En el monolito cada sección envolvía su acceso a
datos en un `try/except` que convertía cualquier error en "no hay datos"; así estuvieron
invisibles durante meses dos bugs que rompían pantallas enteras. Aquí los errores suben con su
status HTTP real. La única excepción deliberada es `/health`, que debe poder reportar fallos sin
fallar él mismo.

**Un solo vocabulario.** El servicio de Riot emite ya los nombres de columna finales (`champion`,
`control_wards`), eliminando el renombrado silencioso `champion_name` → `champion` que era la
fuente de error más frecuente del proyecto.

**Fechas en UTC, visualización configurable.** Ver la cabecera de `migrations/002_timestamptz.sql`.

## Pendiente

Ver `CHECKLIST.md` en la raíz del repo: deuda técnica (v1.3.1), despliegue y features de medio y
largo plazo. Los puntos que históricamente vivieron aquí (config persistida, tests, sync en
background, parche dinámico) ya están implementados.
