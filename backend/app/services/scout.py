"""Escout del rival: de una partida concreta a los campeones que domina ese jugador.

Esto cruza la frontera de Riot (Champion Mastery-V4), por eso la caché en DB es obligatoria:
`scout_cache` (TTL 24h) absorbe la repetición — escoutear 20 partidas del mismo rival cuesta 1
sola llamada a Riot. La traducción `championId` (numérico) -> nombre visible usa la `key` del
índice de campeones de Data Dragon (services/datadragon.py), que ahora la expone a propósito.

Cada respuesta es honesta sobre su origen: `cached` le dice al frontend si la llamada fue
instantánea (caché) o tardó (golpe real a Riot). Los casos "sin datos" no son errores: son
`note`s legibles (rival sin maestrías, puuid ausente, rol sin asignar...).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from backend.app.config import get_settings
from backend.app.repositories import scout as scout_repo
from backend.app.schemas import ScoutMasteryChampion, ScoutOpponent
from backend.app.services import datadragon
from backend.app.services.riot import RiotService, RiotServiceError

log = logging.getLogger(__name__)

SCOUT_TOP_N = 3
_UNKNOWN_ROLES = {"", "UNKNOWN", "INVALID"}


class ScoutUnavailableError(Exception):
    """El destino (Riot o sus metadatos) no deja completar el escout; la UI lo muestra como 503."""


def find_lane_opponent(match_row: dict[str, Any]) -> dict[str, Any] | None:
    """Rival directo de línea dentro del JSONB `participants`.

    Misma heurística que el resto del proyecto (una fila = una partida del usuario, así que su
    campeón lo identifica): el participante del otro equipo con el mismo `team_position`. Si el
    rol es inválido/desconocido, se cae a emparejar por `enemy_champion` (lo que el sync ya
    calculó al guardar la fila).
    """
    participants = match_row.get("participants") or []
    my_champion = str(match_row.get("champion") or "")
    me = next(
        (
            p for p in participants
            if (p.get("champion_name") or "").lower() == my_champion.lower()
        ),
        None,
    )
    if me is None:
        return None

    position = str(me.get("team_position") or "")
    if me.get("team_id") is not None and position.upper() not in _UNKNOWN_ROLES:
        return next(
            (
                p for p in participants
                if p.get("team_id") != me.get("team_id")
                and (p.get("team_position") or "").upper() == position.upper()
            ),
            None,
        )

    enemy_champion = str(match_row.get("enemy_champion") or "")
    return next(
        (
            p for p in participants
            if (p.get("champion_name") or "").lower() == enemy_champion.lower()
        ),
        None,
    )


def top_mastery_champions(
    entries: list[dict[str, Any]],
    name_by_key: dict[str, str],
    limit: int = SCOUT_TOP_N,
) -> list[dict[str, Any]]:
    """Top-N maestrías por puntos, con `championId` numérico traducido a nombre visible.

    Función pura: acepta la respuesta cruda de Riot y un mapa key->nombre (de Data Dragon) y
    devuelve el payload listo para `scout_cache`/respuesta. Sin nombre resuelto (campeón nuevo,
    parche sin metadatos) se muestra la key numérica en vez de inventar un nombre.
    """
    picked = sorted(
        entries,
        key=lambda e: int(e.get("championPoints") or 0),
        reverse=True,
    )[:limit]
    result: list[dict[str, Any]] = []
    for entry in picked:
        key = str(entry.get("championId") or "")
        result.append(
            {
                "champion": name_by_key.get(key) or f"#{key}",
                "champion_key": key,
                "mastery_level": int(entry.get("championLevel") or 0),
                "points": int(entry.get("championPoints") or 0),
            }
        )
    return result


async def _name_by_key() -> dict[str, str]:
    """Mapa key numérica -> nombre visible de todos los campeones del parche vigente."""
    try:
        index = await datadragon.get_champions()
    except RuntimeError:
        log.warning("Sin metadatos de campeones para el escout; los nombres caerán a '#key'")
        return {}
    return {
        str(meta.get("key") or ""): str(meta.get("name") or "")
        for meta in index["champions"].values()
    }


# ──────────────────────────── sección crítica por rival─────────────────────────────
#
# `asyncio.Lock` por `puuid`: dos requests concurrentes para el mismo rival serializan (el
# segundo re-leerá la caché recién llenada por el primero y no tocará Riot). Requests para
# rivales distintos corren en paralelo sin interferirse.
#
# El dict vive solo durante la vida del proceso (single-process by design, ver CLAUDE.md);
# el guard protege la creación de locks para no duplicar en una carrera de `setdefault`.

_scout_locks: dict[str, asyncio.Lock] = {}
_scout_locks_guard = asyncio.Lock()

_SCOUT_ERROR_HINT = (
    "Reintentaré en unos minutos (el fallo queda cacheado para no insistir"
    " mientras Riot esté limitando)."
)


async def _lock_for(puuid: str) -> asyncio.Lock:
    """Lock por rival: serializa llamadas a Riot del mismo puuid sin bloquear rivales distintos."""
    async with _scout_locks_guard:
        lock = _scout_locks.get(puuid)
        if lock is None:
            lock = asyncio.Lock()
            _scout_locks[puuid] = lock
        return lock


async def scout_opponent_for_match(match_row: dict[str, Any]) -> ScoutOpponent:
    """Escoutea al rival de línea de una partida ya cargada en DB.

    Un `asyncio.Lock` por `puuid` evita la carrera de dos requests concurrentes para el
    mismo rival (double-check pattern). La caché negativa (TTL 15 min) impide re-golpear a
    Riot mientras la cuota no se reinicia.
    """
    game_id = str(match_row["game_id"])
    opponent = find_lane_opponent(match_row)

    if opponent is None:
        return ScoutOpponent(
            game_id=game_id,
            opponent_puuid="",
            note="No se pudo identificar al rival de línea en esta partida (rol sin asignar o datos legacy).",
        )

    puuid = str(opponent.get("puuid") or "")
    opponent_champion = str(opponent.get("champion_name") or "")
    opponent_name = str(opponent.get("player_name") or "")
    opponent_role = str(opponent.get("team_position") or "")

    if not puuid:
        return ScoutOpponent(
            game_id=game_id,
            opponent_puuid="",
            opponent_name=opponent_name,
            opponent_champion=opponent_champion,
            opponent_role=opponent_role,
            note="El rival no tiene PUUID registrado (bot o fila legacy): sin maestrías disponibles.",
        )

    async with await _lock_for(puuid):
        return await _scout_locked(
            game_id=game_id,
            puuid=puuid,
            opponent_name=opponent_name,
            opponent_champion=opponent_champion,
            opponent_role=opponent_role,
        )


async def _scout_locked(
    *,
    game_id: str,
    puuid: str,
    opponent_name: str,
    opponent_champion: str,
    opponent_role: str,
) -> ScoutOpponent:
    """Implementación del escout DENTRO del asyncio.Lock por puuid.

    Lee la caché (positiva y negativa) → cache miss → Riot → escribe caché. El double-check
    (re-leer la caché al entrar) garantiza que el segundo request concurrente no vuelve a
    llamar a Riot si el primero ya la llenó.
    """
    now = datetime.now(UTC)
    payload, cached_at, error = await scout_repo.get_scout_cache(puuid)

    # ── Éxito cacheado (TTL 24 h) ─────────────────────────────────────────────
    if payload is not None and scout_repo.cache_is_fresh(cached_at, now):
        log.info("Escout de %s servido desde caché (game %s)", opponent_name, game_id)
        return ScoutOpponent(
            game_id=game_id,
            opponent_puuid=puuid,
            opponent_name=opponent_name,
            opponent_champion=opponent_champion,
            opponent_role=opponent_role,
            top_champions=[ScoutMasteryChampion(**row) for row in payload],
            cached=True,
            cached_at=cached_at,
        )

    # ── Caché negativa fresca (TTL 15 min): 503 sin Riot ──────────────────────
    if error and scout_repo.cache_is_fresh(cached_at, now, ttl=scout_repo.SCOUT_ERROR_TTL):
        log.info("Escout de %s servido de caché negativa (game %s)", opponent_name, game_id)
        raise ScoutUnavailableError(f"{error} {_SCOUT_ERROR_HINT}".strip())

    # ── Cache miss: la llamada real a Riot ─────────────────────────────────────
    try:
        entries = await RiotService(get_settings()).fetch_champion_mastery(puuid)
    except RiotServiceError as exc:
        if exc.status == 404:
            log.info("Riot sin maestrías para %s (cuenta sin partidas o muy reciente)", opponent_name)
            return ScoutOpponent(
                game_id=game_id,
                opponent_puuid=puuid,
                opponent_name=opponent_name,
                opponent_champion=opponent_champion,
                opponent_role=opponent_role,
                note="Riot no tiene maestrías registradas para este rival (sin partidas o cuenta reciente).",
            )
        if exc.retryable:
            # Rate limit o fallo temporal de Riot: guardamos el estado fallido (caché negativa)
            # para no multiplicar las llamadas mientras la cuota no se reinicia.
            await scout_repo.set_scout_cache_error(puuid, str(exc))
            log.warning("Escout de %s fallido (caché negativa): %s", opponent_name, exc)
            raise ScoutUnavailableError(f"{exc} {_SCOUT_ERROR_HINT}".strip()) from exc
        # Error no-retryable (p. ej. 403 key expirada): se informa sin cachear, ya que el
        # problema persistirá y cachingelo ocultaría un error de configuración.
        log.warning("Escout de %s fallido (no-retryable): %s", opponent_name, exc)
        raise ScoutUnavailableError(str(exc)) from exc

    if not entries:
        return ScoutOpponent(
            game_id=game_id,
            opponent_puuid=puuid,
            opponent_name=opponent_name,
            opponent_champion=opponent_champion,
            opponent_role=opponent_role,
            note="Este rival aún no tiene maestrías registradas.",
        )

    top = top_mastery_champions(entries, await _name_by_key())
    await scout_repo.set_scout_cache(puuid, top)

    return ScoutOpponent(
        game_id=game_id,
        opponent_puuid=puuid,
        opponent_name=opponent_name,
        opponent_champion=opponent_champion,
        opponent_role=opponent_role,
        top_champions=[ScoutMasteryChampion(**row) for row in top],
        cached=False,
    )