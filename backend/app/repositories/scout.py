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


async def nemesis(
    user_id: str, min_games: int = 2, limit: int = 5
) -> list[dict[str, Any]]:
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
        WHERE user_id = %s
          AND enemy_champion IS NOT NULL AND enemy_champion <> 'Unknown'
          AND {_NOT_A_REMAKE}
        GROUP BY enemy_champion
        HAVING COUNT(*) >= %s
        ORDER BY winrate ASC, games DESC
        LIMIT %s
        """,
        (user_id, min_games, limit),
    )


async def search_matchups(
    user_id: str, champion: str | None = None, enemy: str | None = None
) -> list[dict[str, Any]]:
    """Busca partidas por campeón propio, enemigo, o ambos. Subcadena e insensible a mayúsculas."""
    conditions: list[str] = ["user_id = %s"]
    params: list[Any] = [user_id]

    if champion:
        conditions.append("champion ILIKE %s")
        params.append(f"%{champion}%")
    if enemy:
        conditions.append("enemy_champion ILIKE %s")
        params.append(f"%{enemy}%")

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
#
# Hay DOS cachés en la misma tabla (columna `error`, migración 011):
#   - Positiva: payload con las maestrías, TTL 24h.
#   - Negativa: `error` con el mensaje del último fallo transitorio (429/5xx), TTL 15 min.
#     Sin ella, un rate limit en vivo se re-expediría con cada reapertura del tab, quemando
#     nuestra propia cuota en el peor momento.

SCOUT_CACHE_TTL = timedelta(hours=24)
# TTL de la caché negativa: 15 minutos de tregua a Riot; tras eso se reintenta en vivo.
SCOUT_ERROR_TTL = timedelta(minutes=15)


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
) -> tuple[list[dict[str, Any]] | None, datetime | None, str]:
    """(payload, cached_at, error) de la caché del Escout, o (None, None, "") si no hay entrada.

    Con `error` no vacío la entrada es una caché NEGATIVA: la última llamada a Riot para este
    rival falló (429/5xx) y `cached_at` indica cuándo. El servicio decide si todavía es válida
    comparando contra SCOUT_ERROR_TTL.
    """
    row = await db.fetch_one(
        "SELECT payload, cached_at, error FROM scout_cache WHERE puuid = %s",
        (puuid,),
    )
    if row is None:
        return None, None, ""
    return row["payload"], row["cached_at"], row["error"]


async def set_scout_cache(puuid: str, payload: list[dict[str, Any]]) -> None:
    """Resultado OK: sobrescribe payload (exitoso) y resetea cached_at; limpia cualquier error anterior."""
    await _upsert_scout_cache(puuid, payload, error="")


async def set_scout_cache_error(puuid: str, error: str) -> None:
    """Estado fallido (caché NEGATIVA): el próximo request se servirá 503 directo sin Riot."""
    await _upsert_scout_cache(puuid, [], error=error)


async def _upsert_scout_cache(
    puuid: str, payload: list[dict[str, Any]], *, error: str
) -> None:
    """Upsert compartido por la caché positiva y la negativa. JSONB admite `[]` vacío."""
    import json

    await db.execute(
        """
        INSERT INTO scout_cache (puuid, payload, cached_at, error)
        VALUES (%s, %s::jsonb, now(), %s)
        ON CONFLICT (puuid) DO UPDATE
            SET payload = EXCLUDED.payload, cached_at = now(), error = EXCLUDED.error
        """,
        (puuid, json.dumps(payload), error),
    )
