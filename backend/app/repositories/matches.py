"""Acceso a la tabla `matches`.

Trampa heredada que aquí se elimina: el monolito recibía de Riot las claves `champion_name` y
`control_wards_bought`, pero las guardaba en las columnas `champion` y `control_wards`. Ese
renombrado silencioso era la fuente de error más común del proyecto. En este backend el servicio
de Riot ya emite los nombres de columna finales, así que hay un solo vocabulario.
"""

from __future__ import annotations

import json
from typing import Any

from backend.app import db

INSERT_COLUMNS = (
    "game_id", "date", "game_version", "champion", "role",
    "kills", "deaths", "assists",
    "cs_total", "cs_min", "control_wards", "win",
    "enemy_champion", "game_duration_minutes",
    "queue_id", "participants",
)

# Campos subjetivos que el usuario puede editar. Whitelist explícita: el nombre de columna
# nunca se interpola desde input del cliente sin pasar por aquí.
UPDATABLE_COLUMNS = frozenset(
    {"lp_change", "tilt_level", "impact_rating", "notes", "vod_review"}
)

# Fila de VALUES multi-fila por statement: demasiado grande y un lote inválido podría degradar
# la transacción completa; demasiado pequeño y se pierde la ventaja de batchear los round-trips.
_INSERT_BATCH_SIZE = 20


_QUEUE_MAP = {
    "ranked": (420, 440),
    "normal": (400, 430),
}

# Mismo criterio que stats.py/scout.py: un remake se registra pero no es una partida real.
# Las filas legacy con duración NULL (pre-esquema) SÍ se conservan en el historial visual;
# a diferencia de La Constitución, aquí no se evalúa disciplina, sólo se muestra historial.
_NOT_A_REMAKE = "(game_duration_minutes IS NULL OR game_duration_minutes >= 5)"


async def list_recent(
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    queue: str | None = None,
) -> list[dict[str, Any]]:
    if queue and queue in _QUEUE_MAP:
        qids = _QUEUE_MAP[queue]
        placeholders = ", ".join(["%s"] * len(qids))
        return await db.fetch_all(
            f"SELECT * FROM matches WHERE user_id = %s AND queue_id IN ({placeholders}) "
            f"AND {_NOT_A_REMAKE} ORDER BY date DESC LIMIT %s OFFSET %s",
            (user_id, *qids, limit, offset),
        )
    return await db.fetch_all(
        f"SELECT * FROM matches WHERE user_id = %s AND {_NOT_A_REMAKE} "
        "ORDER BY date DESC LIMIT %s OFFSET %s",
        (user_id, limit, offset),
    )


async def get_by_id(user_id: str, game_id: str) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT * FROM matches WHERE user_id = %s AND game_id = %s", (user_id, game_id)
    )


async def insert_many(user_id: str, matches: list[dict[str, Any]]) -> int:
    """Inserta partidas nuevas de forma idempotente. Devuelve cuántas eran realmente nuevas.

    Un solo `INSERT ... VALUES (…),(…) ON CONFLICT DO NOTHING` por lote: antes era un INSERT por
    partida (una ida y vuelta de red cada una, ~100 round-trips en un sync grande). Cada lote inválido
    sigue siendo asincrónico por diseño (una partida corrupta no puede cargarse en silencio).

    `user_id` se antepone a las columnas: la PK pasa a ser (user_id, game_id) en la migración
    013, así que el dedupe (ON CONFLICT DO NOTHING) es por usuario y partida.
    """
    if not matches:
        return 0

    column_list = ", ".join(("user_id",) + INSERT_COLUMNS)
    row_placeholders = ", ".join(
        "%s::jsonb" if c == "participants" else "%s"
        for c in INSERT_COLUMNS
    )
    row_placeholders = f"%s, {row_placeholders}"

    def _row_values(m: dict[str, Any]) -> list[Any]:
        values = [user_id]
        for c in INSERT_COLUMNS:
            v = m.get(c)
            if c == "participants" and isinstance(v, list):
                v = json.dumps(v)
            values.append(v)
        return values

    inserted = 0
    for start in range(0, len(matches), _INSERT_BATCH_SIZE):
        chunk = matches[start:start + _INSERT_BATCH_SIZE]
        rows = [_row_values(m) for m in chunk]
        all_placeholders = ", ".join(f"({row_placeholders})" for _ in rows)
        params = tuple(v for row in rows for v in row)
        query = (
            f"INSERT INTO matches ({column_list}) VALUES {all_placeholders} "
            "ON CONFLICT (user_id, game_id) DO NOTHING"
        )
        inserted += await db.execute(query, params)
    return inserted


async def update_details(user_id: str, game_id: str, changes: dict[str, Any]) -> bool:
    """Actualiza campos subjetivos. A diferencia del monolito, un `None` explícito SÍ pone NULL:
    `changes` contiene únicamente las claves que el cliente envió."""
    fields = {k: v for k, v in changes.items() if k in UPDATABLE_COLUMNS}
    if not fields:
        return False

    assignments = ", ".join(f"{col} = %s" for col in fields)
    params = (*fields.values(), user_id, game_id)
    rows = await db.execute(
        f"UPDATE matches SET {assignments} WHERE user_id = %s AND game_id = %s", params
    )
    return rows > 0


async def last_results(user_id: str, limit: int = 3) -> list[dict[str, Any]]:
    """Últimas partidas VÁLIDAS (Ranked Solo/Duo ≥5 min), más reciente primero.

    Ventana que alimenta la Alerta de Tilt del sync (`losing_streak_warning`):
      * `game_duration_minutes >= 5`: un remake se registra pero no es una derrota real;
        contarla disparaba STOP obligatorios falsos. A diferencia de las queries agregadas,
        aquí NO se conservan las filas con duración NULL: la disciplina evalúa partidas
        recientes sincronizadas (siempre con duración), no el historial legacy.
      * `queue_id = 420`: sólo Ranked Solo/Duo cuenta para rachas y muertes; una normal o
        una flex relajan y no deben decidir si sigues jugando ranked.

    Devuelve también champion/deaths/cs_min porque cualquier consumidor futuro de esta
    ventana (rachas, fidelidad al pool, límite de muertes) comparte el mismo criterio.
    """
    return await db.fetch_all(
        """
        SELECT game_id, date, champion, win, deaths, cs_min
        FROM matches
        WHERE user_id = %s AND game_duration_minutes >= 5 AND queue_id = 420
        ORDER BY date DESC LIMIT %s
        """,
        (user_id, limit),
    )


async def newest_unreviewed_ranked(user_id: str, after: Any = None) -> str | None:
    """game_id de la partida Solo/Duo más reciente sin lp_change (review manual pendiente).

    Es la candidata a recibir el delta de LP capturado automáticamente. `after` acota por
    fecha (captured_at del snapshot anterior): un delta acumulado desde entonces no puede
    pertenecer legítimamente a una partida anterior al snapshot.
    """
    if after is not None:
        row = await db.fetch_one(
            """
            SELECT game_id FROM matches
            WHERE user_id = %s AND queue_id = 420 AND lp_change IS NULL AND date > %s
            ORDER BY date DESC LIMIT 1
            """,
            (user_id, after),
        )
    else:
        row = await db.fetch_one(
            "SELECT game_id FROM matches WHERE user_id = %s AND queue_id = 420 "
            "AND lp_change IS NULL ORDER BY date DESC LIMIT 1",
            (user_id,),
        )
    return row["game_id"] if row else None
