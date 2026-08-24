"""Consultas del Scout: nemesis y búsqueda de matchups.

Corrección de consistencia: el monolito usaba `=` (case-sensitive) al buscar por ambos campeones
pero `ILIKE` al buscar sólo por enemigo, así que "jax" encontraba resultados en un caso y no en el
otro. Aquí todo es `ILIKE`. Además la búsqueda sólo-por-campeón-propio, que en Streamlit aceptaba
texto y no hacía nada, sí está implementada.
"""

from __future__ import annotations

from typing import Any

from backend.app import db

_WINRATE = "SUM(CASE WHEN win THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100"

# Mismo criterio que repositories/stats.py: <5 min es remake, no estadística; las filas legacy
# con duración NULL se conservan (desconocido no equivale a remake). Sin esto, los remakes
# contaminan los winrates de rivales y matchups.
_NOT_A_REMAKE = "(game_duration_minutes IS NULL OR game_duration_minutes >= 5)"


async def nemesis(min_games: int = 2, limit: int = 5) -> list[dict[str, Any]]:
    """Campeones enemigos con peor winrate. 'Unknown' se excluye: es el valor que pone
    `_get_enemy_laner` cuando no puede determinar el rival (remakes, roles inválidos)."""
    return await db.fetch_all(
        f"""
        SELECT
            enemy_champion,
            COUNT(*)                             AS games,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) AS wins,
            ROUND({_WINRATE}, 1)                 AS winrate,
            ROUND(AVG(deaths)::numeric, 2)       AS avg_deaths,
            ROUND(AVG(cs_min)::numeric, 2)       AS avg_cs_min
        FROM matches
        WHERE enemy_champion IS NOT NULL AND enemy_champion <> 'Unknown'
          AND {_NOT_A_REMAKE}
        GROUP BY enemy_champion
        HAVING COUNT(*) >= %s
        ORDER BY winrate ASC, games DESC
        LIMIT %s
        """,
        (min_games, limit),
    )


async def search_matchups(
    champion: str | None = None, enemy: str | None = None
) -> list[dict[str, Any]]:
    """Busca partidas por campeón propio, enemigo, o ambos. Subcadena e insensible a mayúsculas."""
    conditions: list[str] = []
    params: list[Any] = []

    if champion:
        conditions.append("champion ILIKE %s")
        params.append(f"%{champion}%")
    if enemy:
        conditions.append("enemy_champion ILIKE %s")
        params.append(f"%{enemy}%")

    if not conditions:
        return []

    # Anti-remake también aquí: un remake listado como "partida contra X" es ruido de review.
    conditions.append(_NOT_A_REMAKE)

    return await db.fetch_all(
        f"SELECT * FROM matches WHERE {' AND '.join(conditions)} ORDER BY date DESC",
        tuple(params),
    )
