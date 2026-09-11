-- 012_sync_runs_partial.sql — nuevo estado 'partial' en sync_runs.
--
-- Sync Reanudable: cuando Riot se degrada a mitad de un sync (429 con Retry-After largo o
-- 5xx sostenidos, RiotDegradedError), el sync ya no termina como 'error' (500) ni miente
-- diciendo 'success'. Se guarda el progreso parcial y el run se cierra como 'partial';
-- `SyncResult.degraded_api` viaja al frontend para que avise y proponga reintentar.
--
-- Idempotente: la CHECK constraída (sin nombre en 006) se regenerea con el mismo nombre
-- que PostgreSQL genera por defecto (sync_runs_status_check).

ALTER TABLE sync_runs DROP CONSTRAINT IF EXISTS sync_runs_status_check;
ALTER TABLE sync_runs ADD CONSTRAINT sync_runs_status_check
    CHECK (status IN ('in_progress', 'success', 'partial', 'error'));