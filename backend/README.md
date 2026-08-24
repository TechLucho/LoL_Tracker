# LoL Tracker — Backend

API REST en FastAPI que reemplaza al monolito Streamlit. Expone los datos de Supabase y de la API
de Riot al frontend, sin que ninguna credencial llegue al navegador.

## Arranque

```powershell
$PY = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"   # el `python` del PATH es el stub de Store

& $PY -m pip install -r backend/requirements.txt
& $PY -m uvicorn backend.app.main:app --reload
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
| `app/services/` | Riot API y lógica de dominio (La Constitución) |
| `app/routers/` | Endpoints HTTP. Sin SQL ni reglas de negocio |
| `migrations/` | Esquema versionado, fuera del runtime |
| `scripts/` | Utilidades operativas (migración del SQLite legacy) |

## Endpoints

| Método | Ruta | Notas |
| --- | --- | --- |
| `GET` | `/health` | Sin auth. Diagnostica credenciales de DB y dev key caducada |
| `GET` | `/api/matches` | `?limit=&offset=` |
| `GET` | `/api/matches/{game_id}` | |
| `PATCH` | `/api/matches/{game_id}` | Campos subjetivos. `null` explícito **borra**; omitir **no toca** |
| `POST` | `/api/sync` | Devuelve `{fetched, inserted, skipped, errors[]}` |
| `GET` | `/api/stats/summary` | Promedios **numéricos**, no strings formateados |
| `GET` | `/api/stats/champions` | Incluye `winrate` y `kda_ratio` calculados en SQL |
| `GET` | `/api/stats/heatmap` | Agrupado en `DISPLAY_TIMEZONE`, no en UTC ni en la tz del servidor |
| `GET` | `/api/stats/lp-trend` | LP acumulado; `has_lp` distingue "0" de "sin registrar" |
| `GET` | `/api/stats/constitution` | Estado anti-tilt: `STOP` / `ON_FIRE` / `NEUTRAL` / `NO_DATA` |
| `GET` | `/api/scout/nemesis` | `?min_games=&limit=` |
| `GET` | `/api/scout/matchups` | `?champion=&enemy=`, ambos `ILIKE` |

## Decisiones de diseño

**Sin `except` genéricos que oculten fallos.** En el monolito cada sección envolvía su acceso a
datos en un `try/except` que convertía cualquier error en "no hay datos"; así estuvieron
invisibles durante meses dos bugs que rompían pantallas enteras. Aquí los errores suben con su
status HTTP real. La única excepción deliberada es `/health`, que debe poder reportar fallos sin
fallar él mismo.

**Los bugs de la Tab 3 y del KDA no se "arreglan": desaparecen por diseño.** `winrate` y
`kda_ratio` se calculan en SQL, y `summary` devuelve números en vez del string `"5.0 / 2.0 / 10.0"`
que la UI tenía que re-parsear.

**Un solo vocabulario.** El servicio de Riot emite ya los nombres de columna finales (`champion`,
`control_wards`), eliminando el renombrado silencioso `champion_name` → `champion` que era la
fuente de error más frecuente del proyecto.

**Fechas en UTC, visualización configurable.** Ver la cabecera de `migrations/002_timestamptz.sql`.

## Pendiente

- `GET/PUT /api/config` para persistir champion pool y OKRs (hoy hardcodeados en la UI)
- Tests con `pytest` + `httpx.AsyncClient`
- `POST /api/sync` como `BackgroundTask` con endpoint de progreso
- Parche de Data Dragon resuelto dinámicamente
