"""El Rosco — salas multijugador (Sprints 1, 3 y 4).

Sprint 1:
  - POST /api/games/rooms                  → crea una sala en 'lobby' (host = tú) y la devuelve
  - POST /api/games/rooms/{room_code}/join → el invitado ocupa el asiento libre en 'lobby', o un
                                             miembro (host/invitado) reconecta en CUALQUIER fase
                                             (rejoin, Regla 1)

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
            current_letter=live_game.current_letter(player),
            completed=player.completed,
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
    """Devuelve la sala al que la pide: rejoin de miembros + entrada de invitados en 'lobby'.

    Rejoin (Regla 1): un MIEMBRO (host o invitado) reconecta en cualquier fase de la partida
    — pérdida de transporte, reinicio del frontend, salida y vuelta — y recibe la sala con 200
    para volver a suscribirse al canal Realtime; se re-difunden el estado de sala y, si la
    partida ya cerró, `game_over`.

    Entrada nueva: solo en 'lobby' un usuario nuevo puede ocupar el asiento libre de invitado
    (claim_guest con guardas atómicas); la sala no avanza de fase por este POST — cuando el host
    esté listo dispara el paso a 'drafting' con POST /state.

    Errores → HTTP 400 (sala inexistente, partida ya empezada para un no-miembro, asiento ocupado).
    """
    code = room_code.strip().upper()

    # Un MIEMBRO (host o invitado) puede RECONECTARSE en cualquier fase (Regla 1: perdidas de
    # transporte, reinicios del frontend o errores de red). Recibe la sala con 200 para volver a
    # suscribirse al canal Realtime; el estado vivo se lo traspasa el árbitro por broadcast y, si
    # hace falta, por el snapshot (rosco) que suele pedir el frontend al reconectar.
    room = await repo.get_room_by_code(code)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La sala no existe.")
    if _role_of(room, user_id) is not None:
        # Re-difundir el estado de la sala: un miembro que reconecta puede haberse perdido el
        # último broadcast (Regla 1). Si la partida ya cerró, _rosco_already_ended re-emite
        # game_over (solo si el motor en memoria fue quien la cerró) para curar al cliente.
        session = live_game.ensure_session(code)
        await realtime_bus.broadcast(code, "state", _live_game_state(room, session).model_dump())
        if room["status"] == "finished":
            await _rosco_already_ended(room, session, code)
        return GameRoom(**room)
    if room["status"] != "lobby":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La partida ya ha empezado en esta sala.")
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


def _winner_id_for(room: dict, outcome: object) -> object:
    """UUID del ganador persistible según la Regla 4 (None si hay empate).

    `outcome` puede ser un `RoscoOutcome`/`TimeoutOutcome` (fin de partida normal) o el propio
    `RoscoGame` (cuando una acción tardía descubre que la partida YA estaba cerrada y hay que
    re-persistir el ganador): todos exponen `winner` (`RoomRole | None`).
    """
    winner = getattr(outcome, "winner", None)
    if winner is None:
        return None
    return room[f"{winner}_id"]


async def _rosco_already_ended(room: dict, session: live_game.LiveSession,
                               code: str) -> RoscoState | None:
    """Si la partida ya acabó en el motor, devuelve su estado final y re-difunde `game_over`.

    Un frontend puede quedarse desincronizado al perder el broadcast de cierre (Regla 1: el
    estado vive en memoria del proceso). En vez de congelarlo con un 400 "El Rosco ya
    terminó", cualquier answer/timeout (o snapshot) tardío recibe la verdad del árbitro con
    200 y se re-emite `game_over` para que el rival atascado también salga de la pantalla.
    Devuelve None si la partida sigue en curso.
    """
    game = session.rosco
    if game is None or not game.ended:
        return None
    if room["status"] != "finished":
        # El cierre original no llegó a la DB (p. ej. el proceso murió a medias): se re-persiste.
        finished = await repo.finish_game(code, _winner_id_for(room, game))
        if finished is not None:
            room = finished
    state = _final_rosco_state(room, session)
    await realtime_bus.broadcast(code, "game_over", state.model_dump())
    return state


def _final_rosco_state(room: dict, session: live_game.LiveSession) -> RoscoState:
    """Estado FINAL del Rosco para clientes que llegan tarde a una partida ya cerrada.

    A diferencia de `_rosco_state`, fuerza `status='finished'` aunque la persistencia del
    cierre no haya llegado a la DB: `current_turn` ya es None por el motor (Regla 4) y un
    `status` coherente evita que el frontend pinte la sala como en curso.
    """
    return _rosco_state({**room, "status": "finished"}, session)


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

    # Nota sobre el orden: el branch de "partida ya acabada" va ANTES que el control de fase.
    # Una sala persistida como 'finished' no pasa `status != 'rosco'`, y precisamente es el
    # cliente desincronizado de UNA partida cerrada el que debe recibir aquí el estado final.
    session = live_game.ensure_session(code)
    ended = await _rosco_already_ended(room, session, code)
    if ended is not None:
        return ended
    if room["status"] != "rosco":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El Rosco no está en curso (fase 'rosco').")

    game = await _ensure_rosco(room, session)
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

    # Mismo orden que en answer: el branch de "partida ya acabada" va ANTES que el control de
    # fase para que un timeout tardío de un cliente desincronizado reciba el estado final (200).
    session = live_game.ensure_session(code)
    ended = await _rosco_already_ended(room, session, code)
    if ended is not None:
        return ended
    if room["status"] != "rosco":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El Rosco no está en curso (fase 'rosco').")

    game = await _ensure_rosco(room, session)
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


@router.get("/rooms/{room_code}/rosco", response_model=RoscoState)
async def get_rosco_snapshot(room_code: str, user_id: CurrentUserId) -> RoscoState:
    """Snapshot actual del Rosco para re-sincronizar a un cliente desincronizado (Regla 1).

    El estado en vivo solo viaja por broadcasts Realtime, que pueden perderse en redes
    inestables: un frontend atascado (letra ya resuelta, su turno cambiado sin enterarse, o la
    partida cerrada sin haber recibido `game_over`) puede pedir aquí la verdad del árbitro SIN
    mutar el juego. Si la partida ya acabó devuelve el estado final, lo que cura a ese cliente
    y, de propina, re-difunde `game_over` hacia el rival atascado.
    """
    code = room_code.strip().upper()
    room = await repo.get_room_by_code(code)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="La sala no existe.")
    if _role_of(room, user_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No estás en esta sala.")
    session = live_game.ensure_session(code)
    game = await _ensure_rosco(room, session)
    if game.ended:
        ended = await _rosco_already_ended(room, session, code)
        if ended is not None:
            return ended
    return _rosco_state(room, session)