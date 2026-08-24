-- 004_participants.sql — almacena los 10 participantes de cada partida como JSONB
-- y añade queue_id para poder filtrar por tipo de cola.

DO $$
BEGIN
    -- participants: JSONB con los 10 jugadores (champion, KDA, CS, KP, items, spells)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches' AND column_name = 'participants'
    ) THEN
        ALTER TABLE matches ADD COLUMN participants JSONB;
        RAISE NOTICE 'Columna participants (JSONB) añadida';
    ELSE
        RAISE NOTICE 'Columna participants ya existe, nada que hacer';
    END IF;

    -- queue_id: ID de la cola de Riot (420=Solo/Duo, 440=Flex, etc.)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches' AND column_name = 'queue_id'
    ) THEN
        ALTER TABLE matches ADD COLUMN queue_id INTEGER;
        RAISE NOTICE 'Columna queue_id añadida';
    ELSE
        RAISE NOTICE 'Columna queue_id ya existe, nada que hacer';
    END IF;
END $$;

-- Índice para filtrar por queue_id
CREATE INDEX IF NOT EXISTS idx_matches_queue_id ON matches (queue_id);
