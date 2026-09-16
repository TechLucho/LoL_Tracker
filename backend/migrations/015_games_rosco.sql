-- 015_games_rosco.sql — v2.3 (Sprint 1): El Rosco — salas multijugador y banco de preguntas.
--
-- El Rosco es el modo multijugador (formato Pasapalabra) que estrena la v2.3. Esta migración
-- aporta la base de datos del Sprint 1:
--   * `game_rooms`      — las partidas en curso, siempre con 2 jugadores (host + invitado).
--   * `rosco_questions` — banco de preguntas A-Z (catálogo global, sembrado por script).
--
-- RLS: `game_rooms` SÍ lleva políticas, pero con una variante sobre el patrón de 013: la fila
-- pertenece a DOS usuarios (host e invitado), así que el aislamiento es la OR de ambos. El
-- backend (rostro `postgres`) sigue pasando por encima del RLS; las políticas blindan el día
-- que una sesión Supabase/JWT toque las tablas directamente.
-- `rosco_questions` NO lleva RLS (excepción consciente, patrón `scout_cache` de 013): es un
-- catálogo de preguntas públicas que nadie "posee"; el único escritor es el seed
-- administrativo `backend/scripts/seed_rosco.py` con credencial de servicio.

CREATE TABLE IF NOT EXISTS game_rooms (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_code   VARCHAR(6)  NOT NULL UNIQUE,
    host_id     UUID        NOT NULL REFERENCES auth.users(id),
    guest_id    UUID        REFERENCES auth.users(id),
    status      VARCHAR     NOT NULL DEFAULT 'lobby'
                CHECK (status IN ('lobby', 'drafting', 'minigames', 'rosco', 'finished')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE game_rooms ENABLE ROW LEVEL SECURITY;

-- Aislamiento de sala: host E invitado ven y mutan su sala compartida. `host` la crea (INSERT
-- con CHECK: el host_id debe ser él), y ambos la leen/actualizan (USING: OR de los dos).
CREATE POLICY user_isolation_game_rooms ON game_rooms
    FOR ALL
    USING (auth.uid() = host_id OR auth.uid() = guest_id)
    WITH CHECK (auth.uid() = host_id OR auth.uid() = guest_id);

CREATE TABLE IF NOT EXISTS rosco_questions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    letter        VARCHAR(1) NOT NULL UNIQUE,
    question_text TEXT       NOT NULL,
    answer        VARCHAR    NOT NULL,
    category      VARCHAR    NOT NULL
);