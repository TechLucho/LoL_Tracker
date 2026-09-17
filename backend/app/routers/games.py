"""El Rosco — salas multijugador (Sprints 1, 3 y 4).

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

Sprint 4 (motor del Rosco, Reglas 1/2/4/5):
  - POST /api/games/rooms/{room_code}/rosco/answer  → resuelve la letra del jugador en turno
                                                      (acierto = sigue, fallo/pasapalabra = rota)
  - POST /api/games/rooms/{room_code}/rosco/timeout → agotamiento del reloj del jugador en turno,
                                                      termina su participación y rota
  La transición minigames → rosco carga las 26 preguntas de `rosco_questions` y arranca el
  motor en memoria (Regla 1); el fin de partida aplica la Regla 4, persiste `winner_id` y
  difunde `game_over`.

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
from backend.app.schemas import (
    DraftPick,
    GameRoom,
    LiveGameState,
    RoscoAnswerInput,
    RoscoLetter,
    RoscoPlayerState,
    RoscoState,
    ScoreInput,
    StateInput,
)
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


async def _ensure_rosco(room: dict, session: live_game.LiveSession) -> live_game.RoscoGame:
    """Devuelve el motor del Rosco de la sala, arrancándolo con las 26 preguntas si falta.

    El motor vive en memoria (Regla 1): si el proceso se reinicia a mitad de un rosco, la sala
    queda 'rosco' en DB pero sin motor; se reconstruye perezosamente al primer answer/timeout.
    """
    game = session.rosco
    if game is not None:
        return game
    if room["status"] != "rosco":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El Rosco no está en fase 'rosco'.")
    rows = await repo.get_rosco_questions()
    if not rows:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="El banco de preguntas está vacío: ejecuta backend/scripts/seed_rosco.py.")
    return live_game.start_rosco(session, rows)


def _rosco_state(room: dict, session: live_game.LiveSession) -> RoscoState:
    """Vuelca el motor del Rosco al contrato que difunden los broadcasts `rosco`/`game_over`."""
    game = session.rosco
    if game is None:
        raise RuntimeError("Motor del Rosco no inicializado en memoria")
    players: dict[str, RoscoPlayerState] = {}
    for role in ("host", "guest"):
        player = game.players[role]
        players[role] = RoscoPlayerState(
            time_remaining=player.time_remaining,
            letters=[
                RoscoLetter(letter=letter,
                            question=game.questions[letter].text,
                            status=player.letters[letter])
                for letter in game.questions
            ],
        )
    return RoscoState(
        room_code=room["room_code"],
        status=room["status"],
        current_turn=game.current_turn,
        players=players,
        winner=game.winner,
        draw=game.draw,
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

    session = live_game.ensure_session(code)
    if target == "minigames" and not session.draft_complete:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El draft no está completo: host y guest deben elegir sobre.")

    updated = await repo.update_status(code, target, room["status"])
    if updated is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Estado obsoleto: otro jugador ya lo cambió. Recarga la sala.")

    state = _live_game_state(updated, session)
    await realtime_bus.broadcast(code, "state", state.model_dump())
    if target == "rosco":
        # Sprint 4: tras la transición se arranca el motor del Rosco en memoria. Si el banco
        # está vacío, la transición ya quedó persistida y el primer answer/timeout reintentará
        # la carga vía _ensure_rosco (el fallo aquí no corrompe nada).
        if session.rosco is None:
            rows = await repo.get_rosco_questions()
            if not rows:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="El banco de preguntas está vacío: ejecuta backend/scripts/seed_rosco.py.")
            live_game.start_rosco(session, rows)
        # Además del contrato de sala, el frontend recibe el estado completo del Rosco (turno
        # + 26 preguntas + letras) para pintar la pantalla sin pedir nada más.
        await realtime_bus.broadcast(code, "rosco", _rosco_state(updated, session).model_dump())
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


# ───────────────────────────── Sprint 4: el Rosco ─────────────────────────────


def _winner_id_for(room: dict, outcome: live_game.RoscoOutcome | live_game.TimeoutOutcome) -> object:
    """UUID del ganador persistible según la Regla 4 (None si hay empate)."""
    if outcome.winner is None:
        return None
    return room[f"{outcome.winner}_id"]


@router.post("/rooms/{room_code}/rosco/answer", response_model=RoscoState)
async def rosco_answer(room_code: str, payload: RoscoAnswerInput,
                       user_id: CurrentUserId) -> RoscoState:
    """Resuelve la letra del jugador en turno (Reglas 2 y 5).

    Acierto → la letra pasa a `success` y el turno se mantiene; fallo → `failed`; pasapalabra
    (respuesta vacía o "pasapalabra") → la letra sigue `pending` para reintentar cuando el turno
    vuelva. En los dos últimos casos el turno rota al rival. Si la partida acabó con este
    movimiento, se aplica la Regla 4, se persiste `winner_id` y se difunde `game_over`.
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
    if room["status"] != "rosco":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El Rosco no está en curso (fase 'rosco').")

    session = live_game.ensure_session(code)
    game = await _ensure_rosco(room, session)
    if game.ended:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El Rosco ya terminó.")
    if game.current_turn != role:
        opp = "El host" if game.current_turn == "host" else "El invitado"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"No es tu turno: {opp} está jugando.")

    letter = payload.letter.strip().upper()
    if letter not in game.questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Letra no válida: {letter!r} no está en el rosco.")
    if game.players[role].letters[letter] != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Esa letra ya está resuelta (solo puedes responder las pendientes).")

    outcome = live_game.answer(game, role, letter, payload.answer, payload.time_remaining)

    if outcome.ended:
        updated = await repo.finish_game(code, _winner_id_for(room, outcome))
        if updated is None:
            updated = await repo.get_room_by_code(code)
            if updated is None:
                updated = {**room, "status": "finished"}
        state = _rosco_state(updated, session)
        await realtime_bus.broadcast(code, "game_over", state.model_dump())
        return state

    state = _rosco_state(room, session)
    await realtime_bus.broadcast(code, "rosco", state.model_dump())
    return state


@router.post("/rooms/{room_code}/rosco/timeout", response_model=RoscoState)
async def rosco_timeout(room_code: str, user_id: CurrentUserId) -> RoscoState:
    """Agotamiento del reloj del jugador en turno: termina su participación y rota (Regla 2).

    Solo puede expirar el reloj del jugador EN TURNO porque los relojes se congelan al pasar
    el turno. El jugador queda a 0s (se acabó para él); si el rival tampoco puede jugar, la
    partida acaba aplicando la Regla 4 y se difunde `game_over`.
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
    if room["status"] != "rosco":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El Rosco no está en curso (fase 'rosco').")

    session = live_game.ensure_session(code)
    game = await _ensure_rosco(room, session)
    if game.ended:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El Rosco ya terminó.")
    if game.current_turn != role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Tu reloj no corre: no es tu turno.")

    outcome = live_game.timeout(game, role)

    if outcome.ended:
        updated = await repo.finish_game(code, _winner_id_for(room, outcome))
        if updated is None:
            updated = await repo.get_room_by_code(code)
            if updated is None:
                updated = {**room, "status": "finished"}
        state = _rosco_state(updated, session)
        await realtime_bus.broadcast(code, "game_over", state.model_dump())
        return state

    state = _rosco_state(room, session)
    await realtime_bus.broadcast(code, "rosco", state.model_dump())
    return state