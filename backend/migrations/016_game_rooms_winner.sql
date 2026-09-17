-- 016_game_rooms_winner.sql — v2.3 (Sprint 4): resultado final del Rosco en `game_rooms`.
--
-- El Rosco termina cuando ambos jugadores agotan su tiempo O resuelven todas sus letras
-- (Regla 2). La Regla 4 (tiebreaker: más aciertos → más tiempo restante → empate) decide el
-- ganador, que se persiste aquí con `winner_id` (NULL cuando hay empate) mientras `status`
-- pasa a 'finished'. `winner_id` queda referenciado a auth.users como host_id/guest_id.

ALTER TABLE game_rooms
    ADD COLUMN IF NOT EXISTS winner_id UUID REFERENCES auth.users(id);