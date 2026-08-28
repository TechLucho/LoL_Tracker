"""Bloc de notas por emparejamiento (vista Matchups).

Tabla de una fila por cruce: `matchup_notes(user_champion, enemy_champion)`. Fila creada
por upsert en el PUT, nunca de antemano, así que el GET devuelve sin error aunque aún no
haya notas guardadas para ese cruce.
"""

from __future__ import annotations

from typing import Any

from backend.app import db


async def get(user_champion: str, enemy_champion: str) -> dict[str, Any] | None:
    """Devuelve la fila de notas del cruce, o None si nunca se guardó nada."""
    return await db.fetch_one(
        """
        SELECT user_champion, enemy_champion, notes, updated_at
        FROM matchup_notes
        WHERE user_champion = %s AND enemy_champion = %s
        """,
        (user_champion, enemy_champion),
    )


async def upsert(user_champion: str, enemy_champion: str, notes: str) -> dict[str, Any]:
    """Guarda/reemplaza las notas del cruce y devuelve el estado resultante."""
    row = await db.fetch_one(  # type: ignore[return-value]
        """
        INSERT INTO matchup_notes (user_champion, enemy_champion, notes, updated_at)
        VALUES (%s, %s, %s, now())
        ON CONFLICT (user_champion, enemy_champion) DO UPDATE SET
            notes      = EXCLUDED.notes,
            updated_at = now()
        RETURNING user_champion, enemy_champion, notes, updated_at
        """,
        (user_champion, enemy_champion, notes),
    )
    if row is None:
        raise RuntimeError(
            "No se pudo escribir matchup_notes. ¿Aplicaste backend/migrations/007_matchup_notes.sql?"
        )
    return row
