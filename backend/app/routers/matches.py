"""Historial de partidas y edición de los campos subjetivos."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.repositories import matches as repo
from backend.app.schemas import Match, MatchUpdate, ScoutOpponent
from backend.app.services.scout import ScoutUnavailableError, scout_opponent_for_match

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("", response_model=list[Match])
async def list_matches(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    queue: str | None = Query(None, description="Filtro: 'ranked' o 'normal'"),
) -> list[Match]:
    rows = await repo.list_recent(limit=limit, offset=offset, queue=queue)
    return [Match(**row) for row in rows]


@router.get("/{game_id}", response_model=Match)
async def get_match(game_id: str) -> Match:
    row = await repo.get_by_id(game_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Partida {game_id} no encontrada")
    return Match(**row)


@router.patch("/{game_id}", response_model=Match)
async def update_match(game_id: str, payload: MatchUpdate) -> Match:
    """Actualiza sólo los campos presentes en el body.

    Enviar `"notes": null` borra las notas; omitir `notes` las deja intactas. El monolito no podía
    distinguir estos dos casos.
    """
    changes = payload.changes()
    if not changes:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El body no contiene ningún campo actualizable.",
        )

    if await repo.get_by_id(game_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Partida {game_id} no encontrada")

    await repo.update_details(game_id, changes)
    row = await repo.get_by_id(game_id)
    return Match(**row)  # type: ignore[arg-type]


@router.get("/{game_id}/scout-opponent", response_model=ScoutOpponent)
async def scout_opponent(game_id: str) -> ScoutOpponent:
    """Escout del rival de línea de una partida: sus 3 campeones más jugados (Champion Mastery).

    La llamada a Riot se hace UNA vez por rival y se cachea en `scout_cache` (TTL 24h) para
    no quemar la cuota escouteando partidas repetidas del mismo jugador. `cached` distingue
    caché caliente de llamada fresca. Cuando no hay datos no se devuelve error: la respuesta
    trae una `note` explicando por qué (rival sin maestrías, rol sin asignar...).
    """
    row = await repo.get_by_id(game_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Partida {game_id} no encontrada")
    try:
        return await scout_opponent_for_match(row)
    except ScoutUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"No se pudo escoutear al rival: {exc}",
        ) from exc
