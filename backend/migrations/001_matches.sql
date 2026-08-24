-- 001_matches.sql — esquema base.
-- Idempotente y no destructivo: refleja la tabla que YA existe en Supabase, sacando el
-- CREATE TABLE del runtime de la aplicación (antes se ejecutaba en cada instanciación).

CREATE TABLE IF NOT EXISTS matches (
    -- Objetivos: los escribe el sync desde Match-V5, una sola vez.
    game_id               TEXT PRIMARY KEY,   -- matchId de Riot, ej. EUW1_7679427728
    date                  TIMESTAMP,
    champion              TEXT    NOT NULL,
    role                  TEXT    NOT NULL,
    kills                 INTEGER NOT NULL,
    deaths                INTEGER NOT NULL,
    assists               INTEGER NOT NULL,
    cs_total              INTEGER NOT NULL,
    cs_min                REAL    NOT NULL,
    control_wards         INTEGER NOT NULL,
    win                   BOOLEAN NOT NULL,
    enemy_champion        TEXT,               -- 'Unknown' cuando no se puede determinar el rival
    game_duration_minutes REAL,

    -- Subjetivos: los rellena el usuario después. Todos nullable a propósito: una partida
    -- sincronizada pero no revisada los tiene vacíos, y las lecturas deben tolerarlo.
    lp_change             INTEGER,
    tilt_level            INTEGER,
    impact_rating         TEXT,
    notes                 TEXT,
    vod_review            BOOLEAN DEFAULT FALSE
);

-- Índices para los patrones de acceso reales de la app.
CREATE INDEX IF NOT EXISTS idx_matches_date        ON matches (date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_enemy       ON matches (enemy_champion);
CREATE INDEX IF NOT EXISTS idx_matches_champion    ON matches (champion);
CREATE INDEX IF NOT EXISTS idx_matches_matchup     ON matches (champion, enemy_champion);

-- Guarda de rango para el tilt (1=Zen, 5=Rage). Se añade sólo si no existe ya.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'matches_tilt_level_range'
    ) THEN
        ALTER TABLE matches ADD CONSTRAINT matches_tilt_level_range
            CHECK (tilt_level IS NULL OR tilt_level BETWEEN 1 AND 5);
    END IF;
END $$;
