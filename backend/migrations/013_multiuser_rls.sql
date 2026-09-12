-- 013_multiuser_rls.sql — v2.0: las tablas transaccionales pasan a pertenecer a un usuario.
--
-- Con la v2.0 cada usuario { principal, partidas, config, syncs, notas, LP } vive bajo su
-- `user_id`. La separación se hace en DOS capas:
--   * Datos:  `user_id UUID NOT NULL REFERENCES auth.users(id)` en cada tabla transaccional.
--   * Acceso: RLS (`FOR ALL USING (auth.uid() = user_id)`). El backend continúa conectando como
--     el rol `postgres` (bypassa RLS); las políticas blindan el día que una sesión Supabase/JWT
--     (anon/authenticated) toque estas tablas directamente.
--
-- IMPORTANTE: `auth.users` y `auth.uid()` SON TERRITORIO SUPABASE. La aplicación jamás escribe
-- en ese schema: Supabase bloquea cualquier intento desde las migraciones de la aplicación
-- con `InsufficientPrivilege: permission denied for schema auth`. Esta migración solo las
-- REFERENCIA (FK + políticas) y asume que o bien la DB es de Supabase (donde ya existen) o el
-- Postgres efímero recibió el stub ANTES de migrar:
--     python -m backend.scripts.seed_auth_stub
--
-- EXCEPCIÓN CONSCIENTE: `scout_cache` SIGUE SIENDO GLOBAL. Es una caché de llamadas a la API de
-- Riot (TTL 24h); compartirla entre usuarios no filtra nada (es información pública de rivales)
-- y evita duplicar llamadas al rate limit. Con username/pUUID de distintos usuarios en la misma
-- tabla, el borrado por TTL se hace igual con `expires_at < now()`.
--
-- REQUISITO EN DEV: la columna entra como `NOT NULL` SIN valor por defecto. Una tabla con filas
-- rompe el `ALTER` ("column ... contains null values"), y ese fallo es intencionado: no hay una
-- asignación honesta del historial pre-v2.0 a un user_id que no existe aún en auth.users. Antes
-- de aplicar esta migración en local hay que vaciarla con:
--     python -m backend.scripts.truncate_tables
-- (En CI / Postgres efímero las tablas nacen vacías y la migración aplica sin pasos previos;
-- la única fila que entorpece es la siembra de `user_settings`, que se limpia aquí abajo.)

-- ── 1. user_settings: de "fila única global" a "fila por usuario" ─────────────────────────
-- Elimina el diseño mono-usuario de 003 (id SMALLINT DEFAULT 1 + CHECK user_settings_single_row).
-- La CHECK de una columna cae con ella; la PK también. La siembra de 003 (id=1) se limpia aquí
-- para que el `ALTER ... NOT NULL` no falle en DB frescas (en dev ya se truncó con el script).

DELETE FROM user_settings;

ALTER TABLE user_settings
    DROP COLUMN IF EXISTS id,
    ADD COLUMN user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE user_settings ADD PRIMARY KEY (user_id);

-- ── 2. matches ────────────────────────────────────────────────────────────────────────────

ALTER TABLE matches
    ADD COLUMN user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_pkey;
ALTER TABLE matches ADD PRIMARY KEY (user_id, game_id);

-- Los accesos reales ahora parten SIEMPRE de un usuario: reemplazo los índices de fecha y
-- matchup "globales" por sus versiones espejo acotadas a user_id.
DROP INDEX IF EXISTS idx_matches_date;
DROP INDEX IF EXISTS idx_matches_matchup;
CREATE INDEX IF NOT EXISTS idx_matches_user_date   ON matches (user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_user_matchup ON matches (user_id, champion, enemy_champion);

-- ── 3. sync_runs ──────────────────────────────────────────────────────────────────────────
-- Mantiene su PK SERIAL (es historia por usuario, no identificador de negocio compartido) y
-- gana user_id + índice de consulta acotado ("últimos runs de ESTE usuario").

ALTER TABLE sync_runs
    ADD COLUMN user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE;

DROP INDEX IF EXISTS idx_sync_runs_started;
CREATE INDEX IF NOT EXISTS idx_sync_runs_user ON sync_runs (user_id, started_at DESC);

-- ── 4. matchup_notes ──────────────────────────────────────────────────────────────────────

ALTER TABLE matchup_notes
    ADD COLUMN user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE matchup_notes DROP CONSTRAINT IF EXISTS matchup_notes_pkey;
ALTER TABLE matchup_notes ADD PRIMARY KEY (user_id, user_champion, enemy_champion);

-- ── 5. lp_snapshots ───────────────────────────────────────────────────────────────────────

ALTER TABLE lp_snapshots
    ADD COLUMN user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE;

DROP INDEX IF EXISTS idx_lp_snapshots_latest;
CREATE INDEX IF NOT EXISTS idx_lp_snapshots_user ON lp_snapshots (user_id, captured_at DESC);

-- ── 6. RLS: aislamiento por usuario ───────────────────────────────────────────────────────

ALTER TABLE matches         ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_runs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE matchup_notes   ENABLE ROW LEVEL SECURITY;
ALTER TABLE lp_snapshots    ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_isolation_matches        ON matches        FOR ALL USING (auth.uid() = user_id);
CREATE POLICY user_isolation_user_settings  ON user_settings  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY user_isolation_sync_runs      ON sync_runs      FOR ALL USING (auth.uid() = user_id);
CREATE POLICY user_isolation_matchup_notes  ON matchup_notes  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY user_isolation_lp_snapshots   ON lp_snapshots   FOR ALL USING (auth.uid() = user_id);