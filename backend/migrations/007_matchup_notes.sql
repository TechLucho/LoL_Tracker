-- 007_matchup_notes.sql — bloc de notas persistente por emparejamiento.
--
-- La vista Matchups deja apuntar estrategias específicas por cruce "Tu campeón
-- contra enemigo": qué niveles de agresividad funcionan, cuándo dodge, cómo jugar
-- la línea. Una fila por (user_champion, enemy_champion), notas libre y updated_at
-- para poder mostrar "última edición". Upsert simple en el PUT.

CREATE TABLE IF NOT EXISTS matchup_notes (
    user_champion   TEXT NOT NULL,
    enemy_champion  TEXT NOT NULL,
    notes           TEXT NOT NULL DEFAULT '',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_champion, enemy_champion)
);
