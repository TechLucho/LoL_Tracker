-- 002_timestamptz.sql — arregla la semántica de las fechas.
--
-- PROBLEMA: el monolito guardaba `datetime.fromtimestamp(...)` sin zona, es decir la hora local
-- de la máquina que ejecutaba el sync, en una columna TIMESTAMP (sin zona). El heatmap
-- "biológico" —cuyo propósito es saber a qué horas del día rindes peor— dependía por tanto de
-- en qué máquina se hubiera sincronizado. Mover el proyecto a un servidor UTC habría desplazado
-- el significado de todas las filas existentes.
--
-- SOLUCIÓN: guardar TIMESTAMPTZ (instante absoluto) y decidir la zona sólo al *consultar*
-- (`date AT TIME ZONE 'Europe/Madrid'` en el heatmap). Así el dato es inequívoco y la
-- visualización es configurable vía DISPLAY_TIMEZONE.
--
-- ⚠️ ASUNCIÓN A CONFIRMAR: las filas ya existentes se interpretan como hora de **Europe/Madrid**
-- (región EUW1 + UI en español). Si sincronizaste desde otra zona, cambia el literal antes de
-- ejecutar. Sólo afecta a las 11 partidas del historial legacy.
--
-- Esta migración es REQUERIDA: las queries del heatmap asumen que `date` es TIMESTAMPTZ.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches'
          AND column_name = 'date'
          AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE matches
            ALTER COLUMN date TYPE TIMESTAMPTZ
            USING date AT TIME ZONE 'Europe/Madrid';
        RAISE NOTICE 'matches.date convertida a TIMESTAMPTZ interpretando Europe/Madrid';
    ELSE
        RAISE NOTICE 'matches.date ya es TIMESTAMPTZ, nada que hacer';
    END IF;
END $$;

-- El índice se reconstruye solo al cambiar el tipo, pero lo dejamos explícito por claridad.
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches (date DESC);
