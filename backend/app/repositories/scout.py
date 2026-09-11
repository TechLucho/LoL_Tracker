"""Consultas del Scout: nemesis y búsqueda de matchups.

Corrección de consistencia: el monolito usaba `=` (case-sensitive) al buscar por ambos campeones
pero `ILIKE` al buscar sólo por enemigo, así que "jax" encontraba resultados en un caso y no en el
otro. Aquí todo es `ILIKE`. Además la búsqueda sólo-por-campeón-propio, que en Streamlit aceptaba
texto y no hacía nada, sí está implementada.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


# ─────────────────────────────── caché del Escout (Riot) ───────────────────────────────
#
# La cuota de Riot es el recurso caro: Champion Mastery-V4 es una llamada por rival, y el mismo
# rival se repite en muchas partidas tuyas. El resultado se guarda aquí (tabla `scout_cache`) y
# se reutiliza durante el TTL, de modo que escoutear 20 partidas del mismo jugador cuesta 1 sola
# llamada a Riot en vez de 20.

SCOUT_CACHE_TTL = timedelta(hours=24)


def cache_is_fresh(cached_at: datetime, now: datetime, ttl: timedelta = SCOUT_CACHE_TTL) -> bool:
    """True si la entrada de la caché aún se puede usar (no ha pasado el TTL).

    Función pura a propósito (sin DB): testeable hermético. Si `cached_at` viene sin zona
    horaria (Postgres devuelve tz-aware, pero por seguridad) se asume UTC igual que `now`.
    """
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now - cached_at <= ttl


async def get_scout_cache(
    puuid: str,
) -> tuple[list[dict[str, Any]] | None, datetime | None]:
    """(payload, cached_at) de la caché del Escout, o (None, None) si no hay entrada."""
    row = await db.fetch_one(
        "SELECT payload, cached_at FROM scout_cache WHERE puuid = %s",
        (puuid,),
    )
    if row is None:
        return None, None
    return row["payload"], row["cached_at"]


async def set_scout_cache(puuid: str, payload: list[dict[str, Any]]) -> None:
    """Sobrescribe la entrada existente (misma persona = mismos datos frescos, TTL se resetea)."""
    import json

    await db.execute(
        """
        INSERT INTO scout_cache (puuid, payload, cached_at)
        VALUES (%s, %s::jsonb, now())
        ON CONFLICT (puuid) DO UPDATE
            SET payload = EXCLUDED.payload, cached_at = now()
        """,
        (puuid, json.dumps(payload)),
    )
