-- 011_scout_cache_error.sql — caché negativa para fallos transitorios del Escout.
--
-- Cuando Riot devuelve 429 (rate limit) o un 5xx al consultar Champion Mastery, no hay
-- maestrías que cachear pero SÍ conviene recordar "esto falló hace poco": re-expedir la misma
-- llamada a los pocos segundos empeora el rate limit en vez de arreglarlo. El estado fallido
-- se guarda en `error` y se reutiliza durante SCOUT_ERROR_TTL (15 min, verificado en Python
-- en repositories/scout.py) sirviendo un 503 directo sin golpear la API de Riot.
--
-- Idempotente por diseño: un segundo ALTER no tiene efecto y no rompe la migración 010.
ALTER TABLE scout_cache ADD COLUMN IF NOT EXISTS error TEXT NOT NULL DEFAULT '';