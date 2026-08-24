"""Scout: nemesis y búsqueda en la base de conocimiento de matchups."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.repositories import scout as repo
from backend.app.schemas import Match, Nemesis

router = APIRouter(prefix="/api/scout", tags=["scout"])


@router.get("/nemesis", response_model=list[Nemesis])
async def nemesis(
    min_games: int = Query(2, ge=1),
    limit: int = Query(5, ge=1, le=20),
) -> list[Nemesis]:
    return [Nemesis(**row) for row in await repo.nemesis(min_games=min_games, limit=limit)]


@router.get("/matchups", response_model=list[Match])
async def matchups(
    champion: str | None = Query(None, description="Campeón propio (subcadena, case-insensitive)"),
    enemy: str | None = Query(None, description="Campeón enemigo (subcadena, case-insensitive)"),
) -> list[Match]:
    """Busca por campeón propio, enemigo o ambos.

    Ambos filtros usan `ILIKE`: en Streamlit la búsqueda con los dos campos era case-sensitive y
    la de sólo-enemigo no, así que "jax" funcionaba en un caso y no en el otro. Además, buscar
    sólo por campeón propio aquí sí devuelve resultados (antes el input no hacía nada).
    """
    if not champion and not enemy:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Indica al menos `champion` o `enemy`.",
        )
    return [Match(**row) for row in await repo.search_matchups(champion=champion, enemy=enemy)]
