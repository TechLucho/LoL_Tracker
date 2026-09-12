"""Registro de auditoría de sincronizaciones (migración 006).

Cada POST /api/sync crea un registro con estado 'in_progress' que se actualiza
al terminar (success o error). La tabla es append-only: consultas típicas son
"últimos N runs" y "runs fallidos recientes".
"""

from __future__ import annotations

from typing import Any

from backend.app import db


async def start_run(user_id: str, started_at: Any) -> int:
    """Crea un registro con status='in_progress'. Devuelve el id para actualizar después."""
    async with db.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO sync_runs (user_id, started_at, status)
            VALUES (%s, %s, 'in_progress')
            RETURNING id
            """,
            (user_id, started_at),
        )
        row = await cur.fetchone()
        return row["id"] if row else 0


async def finish_run(
    run_id: int,
    *,
    status: str,
    finished_at: Any,
    matches_added: int = 0,
    error_message: str | None = None,
) -> None:
    """Actualiza el registro al terminar el sync."""
    await db.execute(
        """
        UPDATE sync_runs
        SET finished_at = %s, status = %s, matches_added = %s, error_message = %s
        WHERE id = %s
        """,
        (finished_at, status, matches_added, error_message, run_id),
    )


async def recent_runs(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Últimos N sync runs de un usuario, más reciente primero."""
    return await db.fetch_all(
        """
        SELECT id, started_at, finished_at, status, matches_added, error_message
        FROM sync_runs
        WHERE user_id = %s
        ORDER BY started_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )
