-- 010_scout_cache.sql — caché de maestrías de campeones del rival (Champion Mastery-V4).
--
-- El Escout consulta la API de Riot una vez por rival de línea; la cuota de la key está
-- limitada, así que el resultado se guarda en DB y se reutiliza (TTL 24h, verificado en
-- Python en repositories/scout.py) en vez de golpear a Riot por cada partida del mismo rival.
-- La clave es el PUUID: la misma persona repite como rival en muchas partidas tuyas.

CREATE TABLE IF NOT EXISTS scout_cache (
    puuid       TEXT PRIMARY KEY,
    payload     JSONB NOT NULL,
    cached_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);