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


async def scout_opponent_for_match(match_row: dict[str, Any]) -> ScoutOpponent:
    """Escoutea al rival de línea de una partida ya cargada en DB.

    La llamada a Riot solo ocurre en `cache miss` (y se guarda el resultado); en `cache hit`
    la respuesta sale sin tocar la API de Riot en absoluto.
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

    now = datetime.now(UTC)
    payload, cached_at = await scout_repo.get_scout_cache(puuid)
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
        log.warning("Escout de %s fallido: %s", opponent_name, exc)
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