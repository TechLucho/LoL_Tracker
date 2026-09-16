"""El Rosco — salas multijugador (Sprint 1).

- POST /api/games/rooms                  → crea una sala en 'lobby' (host = tú) y la devuelve
- POST /api/games/rooms/{room_code}/join → el invitado ocupa el asiento libre (lobby → drafting)

El código de sala son 6 letras mayúsculas generadas con `secrets` (criptográficamente seguras).
Al ser UNIQUE en `game_rooms`, una colisión (26^6 ≈ 3×10^8 combinaciones, pero puede pasar) se
reintenta con un código nuevo.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status
from psycopg.errors import UniqueViolation

from backend.app.deps import CurrentUserId
from backend.app.repositories import games as repo
from backend.app.schemas import GameRoom

router = APIRouter(prefix="/api/games", tags=["games"])

_ROOM_CODE_LENGTH = 6
_ROOM_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ROOM_CODE_TRIES = 5


def _generate_room_code() -> str:
    return "".join(secrets.choice(_ROOM_CODE_ALPHABET) for _ in range(_ROOM_CODE_LENGTH))


@router.post("/rooms", response_model=GameRoom)
async def create_room(user_id: CurrentUserId) -> GameRoom:
    """Crea una sala en 'lobby' con el usuario como host y devuelve el código para compartir."""
    for _ in range(_ROOM_CODE_TRIES):
        code = _generate_room_code()
        try:
            row = await repo.create_room(code, user_id)
        except UniqueViolation:
            # Código ya usado por otra sala (UNIQUE de game_rooms): probar con uno nuevo.
            continue
        if row is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="No se pudo crear la sala.")
        return GameRoom(**row)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="No se pudo generar un código de sala único.")


@router.post("/rooms/{room_code}/join", response_model=GameRoom)
async def join_room(room_code: str, user_id: CurrentUserId) -> GameRoom:
    """El invitado reivindica el asiento libre; la sala pasa de 'lobby' a 'drafting'.

    Errores → HTTP 400 (sala inexistente/fuera de lobby, asiento ocupado, o el host intentando
    unirse a su propia sala).
    """
    code = room_code.strip().upper()
    room = await repo.find_lobby_by_code(code)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La sala no existe o ya no está en 'lobby'.")
    if room["host_id"] == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No puedes unirte a tu propia sala.")
    claimed = await repo.claim_guest(code, user_id)
    if claimed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La sala ya tiene invitado.")
    return GameRoom(**claimed)