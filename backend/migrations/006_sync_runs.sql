-- 006_sync_runs.sql — auditoría de sincronizaciones.
--
-- Cada ejecución de sync queda registrada con timestamps de inicio/fin, estado final,
-- número de partidas nuevas y mensaje de error si falló. La tabla es append-only:
-- cada POST /api/sync crea una fila nueva. Esto reemplaza la información que antes
-- vivía sólo en memoria (_SyncState) y se perdía al reiniciar uvicorn.
--
-- _SyncState se mantiene para el polling rápido del frontend (/api/sync/status);
-- sync_runs es la fuente de verdad histórica.

CREATE TABLE IF NOT EXISTS sync_runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,                        -- NULL mientras corre
    status          TEXT NOT NULL CHECK (status IN ('in_progress', 'success', 'error')),
    matches_added   INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT                                -- NULL en éxito
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON sync_runs (started_at DESC);
