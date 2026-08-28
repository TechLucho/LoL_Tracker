"""Bloc de notas persistente por emparejamiento (vista Matchups)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.repositories import matchup_notes as repo
from backend.app.schemas import MatchupNotes, MatchupNotesUpdate

router = APIRouter(prefix="/api/matchup-notes", tags=["matchup-notes"])


def _empty(user_champion: str, enemy_champion: str) -> MatchupNotes:
    """Notas vacías para un cruce que aún no tiene fila guardada."""
    return MatchupNotes(user_champion=user_champion, enemy_champion=enemy_champion, notes="")


@router.get("/{user_champion}/{enemy_champion}", response_model=MatchupNotes)
async def get_notes(user_champion: str, enemy_champion: str) -> MatchupNotes:
    """Notas del cruce. Si nunca se guardó nada, devuelve notas vacías (no 404)."""
    row = await repo.get(user_champion, enemy_champion)
    if row is None:
        return _empty(user_champion, enemy_champion)
    return MatchupNotes(**row)


@router.put("/{user_champion}/{enemy_champion}", response_model=MatchupNotes)
async def put_notes(user_champion: str, enemy_champion: str, payload: MatchupNotesUpdate) -> MatchupNotes:
    """Guarda/reemplaza las notas del cruce (PUT semantics)."""
    if not user_champion or not enemy_champion:
        raise HTTPException(422, "Faltan los campeones en la URL.")
    row = await repo.upsert(user_champion, enemy_champion, payload.notes)
    return MatchupNotes(**row)
