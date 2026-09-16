"""Salas del Rosco (Sprint 1): acceso a `game_rooms`.

SQL crudo sobre la tabla de la migración 015. El flujo del lobby es:
  1. `create_room`         — el host crea la sala en 'lobby' y obtiene el código compartible.
  2. `find_lobby_by_code`  — el invitado localiza la sala por el código (solo estados 'lobby').
  3. `claim_guest`         — UPDATE con guardas atómicas: la sala debe estar en 'lobby', el
                            asiento de invitado libre y el solicitante no puede ser el host.
"""

from __future__ import annotations

from uuid import UUID

from backend.app import db

_INSERT_ROOM = """
INSERT INTO game_rooms (room_code, host_id)
VALUES (%s, %s)
RETURNING *
"""

_GET_ROOM_BY_CODE = """
SELECT * FROM game_rooms
WHERE room_code = %s AND status = 'lobby'
"""

_CLAIM_GUEST = """
UPDATE game_rooms
SET guest_id = %s
WHERE room_code = %s
  AND status = 'lobby'
  AND guest_id IS NULL
  AND host_id <> %s
RETURNING *
"""

_GET_ROOM_BY_CODE_ANY = """
SELECT * FROM game_rooms
WHERE room_code = %s
"""

_UPDATE_STATUS = """
UPDATE game_rooms
SET status = %s
WHERE room_code = %s
  AND status = %s
RETURNING *
"""


async def create_room(room_code: str, host_id: UUID) -> dict | None:
    """Crea una sala en 'lobby' con `host_id` como anfitrión y la devuelve (RETURNING *)."""
    return await db.fetch_one(_INSERT_ROOM, (room_code, host_id))


async def find_lobby_by_code(room_code: str) -> dict | None:
    """Devuelve la sala en 'lobby' con ese código, o None si no existe / ya no es lobby."""
    return await db.fetch_one(_GET_ROOM_BY_CODE, (room_code,))


async def claim_guest(room_code: str, guest_id: UUID) -> dict | None:
    """Ocupa el asiento de invitado SIN mover la sala de estado (sigue en 'lobby').

    El paso lobby → drafting lo dispara el host deliberadamente con POST /state, de modo que
    el invitado no roza el draft antes de que el host esté listo (ver routers/games.py).
    None si ya no estaba libre. Guardas atómicas en el UPDATE: `status='lobby'`,
    `guest_id IS NULL`, `host_id <> guest` (el invitado no puede ser el host).
    """
    return await db.fetch_one(_CLAIM_GUEST, (guest_id, room_code, guest_id))


async def get_room_by_code(room_code: str) -> dict | None:
    """Devuelve la sala en CUALQUIER estado por su código, o None si no existe."""
    return await db.fetch_one(_GET_ROOM_BY_CODE_ANY, (room_code,))


async def update_status(room_code: str, new_status: str, expected_old: str) -> dict | None:
    """Transición atómica de estado: cambia `status` solo si sigue siendo `expected_old`.

    Devuelve la sala actualizada, o None si otro request ya la movió (conflicto de transición).
    """
    return await db.fetch_one(_UPDATE_STATUS, (new_status, room_code, expected_old))