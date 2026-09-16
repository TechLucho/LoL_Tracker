"""El Rosco — salas multijugador (Sprints 1 y 3).

Sprint 1:
  - POST /api/games/rooms                  → crea una sala en 'lobby' (host = tú) y la devuelve
  - POST /api/games/rooms/{room_code}/join → el invitado ocupa el asiento libre y la sala SIGUE
                                             en 'lobby'; el host decide cuándo pasar a 'drafting'

Sprint 3 (draft + minijuegos + banco de tiempo, Regla 3):
  - POST /api/games/rooms/{room_code}/state → avanza la máquina de estados en la DB
                                             (lobby → drafting → minigames → rosco → finished)
  - POST /api/games/rooms/{room_code}/draft → host y guest eligen 1 categoría alternando turnos
  - POST /api/games/rooms/{room_code}/score → convierte puntos de minijuego en segundos y los
                                             suma al banco INDIVIDUAL en memoria (Servidor = árbitro)

El código de sala son 6 letras mayúsculas generadas con `secrets` (criptográficamente seguras).
Al ser UNIQUE en `game_rooms`, una colisión (26^6 ≈ 3×10^8 combinaciones, pero puede pasar) se
reintenta con un código nuevo. Cada mutación de estado difunde el estado vivo por Realtime
(`room:{code}`) para que ambos frontends cambien de pantalla sin refrescar.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status
from psycopg.errors import UniqueViolation

from backend.app.deps import CurrentUserId
from backend.app.repositories import games as repo
from backend.app.schemas import DraftPick, GameRoom, LiveGameState, ScoreInput, StateInput
from backend.app.services import live_game
from backend.app.services import realtime_bus

router = APIRouter(prefix="/api/games", tags=["games"])

_ROOM_CODE_LENGTH = 6
_ROOM_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ROOM_CODE_TRIES = 5

# Máquina de estados de la partida (Sprint 3): qué transiciones están permitidas. `lobby →
# drafting` solo la dispara el HOST (requiere invitado en la sala, validado en el endpoint);
# `drafting → minigames` exige además el draft completo (las dos categorías elegidas).
_STATE_TRANSITIONS: dict[str, set[str]] = {
    "lobby": {"drafting"},
    "drafting": {"minigames"},
    "minigames": {"rosco"},
    "rosco": {"finished"},
}


def _generate_room_code() -> str:
    return "".join(secrets.choice(_ROOM_CODE_ALPHABET) for _ in range(_ROOM_CODE_LENGTH))


def _role_of(room: dict, user_id) -> str | None:
    """Rol del usuario dentro de la sala ('host' | 'guest'), o None si no es miembro."""
    if room["host_id"] == user_id:
        return "host"
    if room["guest_id"] == user_id:
        return "guest"
    return None


def _live_game_state(room: dict, session: live_game.LiveSession) -> LiveGameState:
    """Vuelca la sala + sesión en vivo al contrato que difunden los broadcasts Realtime."""
    return LiveGameState(
        room_code=room["room_code"],
        status=room["status"],
        draft_turn=session.draft_turn,
        draft_picks=dict(session.draft_picks),
        time_banks={r: live_game.bank_seconds(session, r) for r in ("host", "guest")},
    )


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
    """El invitado reivindica el asiento libre; la sala permanece en 'lobby'.

    Cuando el host esté listo, dispara el paso a 'drafting' con POST /state. De este modo el
    invitado que se une no salta él solo al Draft antes de que el host lo inicie.
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
    # Difunde el estado de la sala por si el host tiene otra pestaña esperando en el lobby.
    session = live_game.ensure_session(code)
    await realtime_bus.broadcast(code, "state", _live_game_state(claimed, session).model_dump())
    return GameRoom(**claimed)


# ───────────────────────── Sprint 3: draft y minijuegos ─────────────────────────


@router.post("/rooms/{room_code}/state", response_model=LiveGameState)
async def advance_state(room_code: str, payload: StateInput, user_id: CurrentUserId) -> LiveGameState:
    """Avanza la máquina de estados (lobby → drafting → minigames → rosco → finished).

    Solo puede llamarlo un miembro de la sala. `lobby → drafting` requiere un invitado en la
    sala (sin guest nadie puede jugar el Draft) y `drafting → minigames` exige que el draft
    esté completo (host y guest con su categoría). La transición se ejecuta con un UPDATE
    atómico sobre `game_rooms.status` (compare-and-swap) y se difunde por Realtime.
    """
    code = room_code.strip().upper()
    room = await repo.get_room_by_code(code)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La sala no existe.")
    if _role_of(room, user_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No estás en esta sala.")

    target = payload.status
    allowed = _STATE_TRANSITIONS.get(room["status"], set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transición no permitida: {room['status']} → {target}. "
                   f"Permitidas: {sorted(allowed) or 'ninguna'}.",
        )

    if target == "drafting" and room["guest_id"] is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No se puede empezar el Drafting sin un invitado en la sala.")

    if target == "minigames" and not live_game.ensure_session(code).draft_complete:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El draft no está completo: host y guest deben elegir sobre.")

    updated = await repo.update_status(code, target, room["status"])
    if updated is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Estado obsoleto: otro jugador ya lo cambió. Recarga la sala.")

    session = live_game.ensure_session(code)
    state = _live_game_state(updated, session)
    await realtime_bus.broadcast(code, "state", state.model_dump())
    return state


@router.post("/rooms/{room_code}/draft", response_model=LiveGameState)
async def draft_category(room_code: str, payload: DraftPick, user_id: CurrentUserId) -> LiveGameState:
    """El jugador cuyo turno toque elige una categoría de `DRAFT_CATEGORIES`.

    Turno alterno: el host elige primero, luego el guest; cuando ambos han elegido el draft se
    da por completado (`draft_turn` → None) y `…/state → minigames` se desbloquea. El estado
    en vivo del draft vive en memoria (Regla 1) y se difunde por Realtime.
    """
    code = room_code.strip().upper()
    room = await repo.get_room_by_code(code)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La sala no existe.")
    role = _role_of(room, user_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No estás en esta sala.")
    if room["status"] != "drafting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El draft solo puede jugarse en la fase 'drafting'.")

    category = payload.category.strip()
    session = live_game.ensure_session(code)

    if session.draft_turn is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El draft ya está completado: ambas categorías elegidas.")
    if session.draft_turn != role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"No es tu turno de draft: le toca al {'host' if session.draft_turn == 'host' else 'invitado'}.")
    if role in session.draft_picks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Ya elegiste tu categoría.")
    if category not in live_game.DRAFT_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Categoría no válida. Válidas: {list(live_game.DRAFT_CATEGORIES)}.")
    if category in session.draft_picks.values():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Esa categoría ya la eligió el rival.")

    live_game.apply_draft_pick(session, role, category)
    state = _live_game_state(room, session)
    await realtime_bus.broadcast(code, "draft", state.model_dump())
    return state


@router.post("/rooms/{room_code}/score", response_model=LiveGameState)
async def submit_score(room_code: str, payload: ScoreInput, user_id: CurrentUserId) -> LiveGameState:
    """Regla 3: suma `points` al banco individual de tiempo del jugador (1 punto = 1 segundo).

    Validación exhaustiva en el servidor (el frontend es "tonto"): la sala debe estar en
    'minigames', el autor debe ser miembro y `points` ∈ [1, 100]. El banco (100s base + lo
    ganado por él mismo) vive en memoria y se difunde por Realtime.
    """
    code = room_code.strip().upper()
    room = await repo.get_room_by_code(code)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La sala no existe.")
    role = _role_of(room, user_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No estás en esta sala.")
    if room["status"] != "minigames":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Los minijuegos aún no han empezado (fase 'minigames').")

    session = live_game.ensure_session(code)
    live_game.add_score(session, role, payload.points)
    state = _live_game_state(room, session)
    await realtime_bus.broadcast(code, "score", state.model_dump())
    return state