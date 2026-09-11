-- 008_game_version.sql — guarda la versión de Riot del parche de cada partida.
-- Alimenta la Alerta de Parche (backend/app/repositories/stats.py -> patch_alert):
-- compara el winrate de los campeones del pool en el parche actual vs. los anteriores.
-- Legacy (filas sin juego de parche aún): NULL = "parche desconocido", que cuenta
-- como historial previo y nunca como partida del parche actual.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches' AND column_name = 'game_version'
    ) THEN
        ALTER TABLE matches ADD COLUMN game_version TEXT;
        RAISE NOTICE 'Columna game_version (TEXT) añadida';
    ELSE
        RAISE NOTICE 'Columna game_version ya existe, nada que hacer';
    END IF;
END $$;