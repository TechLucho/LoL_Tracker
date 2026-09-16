"""Caché del Escout de rivales (Champion Mastery de Riot).

La consulta de nemesis y matchups vivió aquí para el router /api/scout/*, retirado junto con
su página (2026-08-24). Lo que queda es la mitad VIVA: la caché que evita quemar la cuota de
Riot al escoutear el rival de línea desde el Match Accordion (`/api/matches/{game_id}/scout-opponent`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app import db


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
