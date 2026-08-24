"""Historial de partidas y edición de los campos subjetivos."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.repositories import matches as repo
from backend.app.schemas import Match, MatchUpdate

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
