-- 005_lp_snapshots.sql — auto-tracker de LP de Ranked Solo/Duo.
--
-- En cada sync se consulta League-V4 y se guarda un snapshot del LP actual. El delta entre
-- snapshots consecutivos alimenta `matches.lp_change` automáticamente (en la partida ranked
-- más reciente que aún no tenga review manual), de modo que la gráfica de LP acumulado se
-- llena sola sin intervención del usuario.
--
-- Limitaciones aceptadas por diseño:
--   * Riot ya NO expone el LP por partida; sólo podemos capturar el estado actual. Si un sync
--     trae varias partidas nuevas, el delta neto completo se asigna a la más reciente y las
--     intermedias quedan con lp_change NULL (la gráfica las trata como 0: la acumulada es
--     correcta, la repartición por partida es aproximada).
--   * Dodges, promos y decaimiento alteran el LP sin generar partida: el delta sigue siendo
--     matemáticamente correcto en la acumulada, aunque su origen no sea una partida concreta.

CREATE TABLE IF NOT EXISTS lp_snapshots (
    id          SERIAL PRIMARY KEY,
    riot_id     TEXT        NOT NULL,                -- 'Nombre#TAG' (mono-usuario, pero trazable)
    lp          INTEGER     NOT NULL CHECK (lp >= 0),
    tier        TEXT,                                -- 'GOLD', 'PLATINUM', ...
    division    TEXT,                                -- Riot lo llama 'rank' ('IV'..'I')
    wins        INTEGER,
    losses      INTEGER,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lp_snapshots_latest ON lp_snapshots (riot_id, captured_at DESC);
