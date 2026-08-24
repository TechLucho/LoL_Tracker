"""Snapshots de LP de Solo/Duo capturados automáticamente al final de cada sync.

Tabla `lp_snapshots` (migración 005). Un sync sin snapshot previo sólo crea la línea base;
a partir del segundo, el delta entre snapshots se escribe como `lp_change` en la partida
ranked más reciente sin review manual (ver `_assign_lp_delta` en routers/sync.py).
"""

from __future__ import annotations

from typing import Any

from backend.app import db


async def latest_snapshot(riot_id: str) -> dict[str, Any] | None:
    """Último snapshot guardado para este Riot ID, o None si nunca se capturó LP."""
    return await db.fetch_one(
        """
        SELECT riot_id, lp, tier, division, wins, losses, captured_at
        FROM lp_snapshots
        WHERE riot_id = %s
        ORDER BY captured_at DESC
        LIMIT 1
        """,
        (riot_id,),
    )


async def insert_snapshot(
    riot_id: str,
    *,
    lp: int,
    tier: str | None = None,
    division: str | None = None,
    wins: int | None = None,
    losses: int | None = None,
) -> None:
    """Guarda el estado actual del ladder. Nunca actualiza: cada sync es una fila nueva."""
    await db.execute(
        """
        INSERT INTO lp_snapshots (riot_id, lp, tier, division, wins, losses)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (riot_id, lp, tier, division, wins, losses),
    )
