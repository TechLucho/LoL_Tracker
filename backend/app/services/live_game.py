"""El Rosco — estado vivo de la partida en memoria (Sprints 3 y 4).

Sigue la Regla 1 de CHECKLIST: el backend es el árbitro y fuente de verdad; la DB
(`game_rooms`) persiste emparejamiento, estado de la máquina y resultado final, pero NO el
estado en vivo. Lo que aquí guardamos por `room_code` es exactamente eso, el estado vivo:

  * `draft_turn`  — a quién le toca elegir categoría ('host' arranca siempre).
  * `draft_picks` — categoría elegida por rol (1 cada uno, de DRAFT_CATEGORIES).
  * `extra_seconds` — segundos ganados por rol en los minijuegos (Regla 3).
  * `rosco` — el motor del Rosco (Sprint 4): 26 preguntas, turnos y relojes.

MONO-PROCESO: igual que `_SyncState` y las métricas, esto vive en la memoria del proceso.
`main._assert_single_process` ya impide levantar con varios workers; si además el proceso
se reinicia a mitad de una partida, el rosco se pierde (los ESTADOS persisten en DB, el
emparejamiento también y `session.rosco` se reconstruye perezosamente pidiendo las 26
preguntas al primer answer/timeout) — aceptable para el Sprint 4.

El motor del Rosco (Sección "Sprint 4") implementa:
  * Regla 2 — acierto sigue el turno; fallo/pasapalabra congela el reloj y pasa al rival.
  * Regla 4 — tiebreaker al acabar: más aciertos, después más tiempo restante, tercero empate.
  * Regla 5 — las respuestas se comparan vía `normalize_answer` (utils/text.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from backend.app.utils.text import normalize_answer

Role = str  # 'host' | 'guest'

# Regla 3: cada jugador arranca con un banco base de 100 segundos.
BASE_TIME_BANK_SECONDS = 100.0

# Regla 3: conversión de puntos de minijuego a segundos extras (1 punto = 1 segundo).
SECONDS_PER_POINT = 1.0

# Categorías del Draft (lista estática de prueba, Sprint 3). COINCIDEN con las del seed de 26
# preguntas (backend/scripts/seed_rosco.py): así una categoría elegida en el Draft tiene
# preguntas reales en el Rosco (Sprint 4). El catálogo masivo de categorías llega en el
# Sprint 5 — mantener el frontend (DraftingPhase) sincronizado con esta lista.
DRAFT_CATEGORIES = ("Lore", "Mecánicas", "Jugabilidad")

# Las 26 letras del Rosco (A-Z).
ROSCO_LETTERS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

LetterStatus = Literal["pending", "success", "failed"]


@dataclass
class LiveSession:
    draft_turn: Role | None = "host"  # el host elige primero
    draft_picks: dict[Role, str] = field(default_factory=dict)
    extra_seconds: dict[Role, float] = field(default_factory=dict)
    rosco: RoscoGame | None = None  # Sprint 4: motor del Rosco (None = sin empezar)

    @property
    def draft_complete(self) -> bool:
        return len(self.draft_picks) == 2


# Estado vivo por sala. Acceso directo al dict: la app es mono-proceso y el event loop de
# FastAPI serializa los handlers (no hay await dentro de la mutación), así que no hay carreras.
_sessions: dict[str, LiveSession] = {}


def ensure_session(room_code: str) -> LiveSession:
    """Devuelve la sesión en vivo de la sala, creándola con los valores base si falta."""
    session = _sessions.get(room_code)
    if session is None:
        session = LiveSession()
        _sessions[room_code] = session
    return session


def drop_session(room_code: str) -> None:
    """Elimina la sesión en vivo (sala cerrada / partida terminada)."""
    _sessions.pop(room_code, None)


def bank_seconds(session: LiveSession, role: Role) -> float:
    """Banco del jugador: Regla 3 → 100 segundos base + segundos ganados por ÉL MISMO."""
    return BASE_TIME_BANK_SECONDS + session.extra_seconds.get(role, 0.0)


def apply_draft_pick(session: LiveSession, role: Role, category: str) -> None:
    """Registra la elección de categoría de `role` y alterna el turno (Regla del Draft).

    Validaciones previas (turno, duplicados, categoría válida) corren en el router antes de
    entrar aquí: este método solo muta el estado de forma determinista.
    """
    session.draft_picks[role] = category
    other: Role = "guest" if role == "host" else "host"
    session.draft_turn = other if other not in session.draft_picks else None


def add_score(session: LiveSession, role: Role, points: int) -> float:
    """Regla 3: convierte puntos de minijuego en segundos y los suma al banco INDIVIDUAL.

    Devuelve el banco resultante (en segundos) para que el endpoint lo difunda por Realtime.
    """
    session.extra_seconds[role] = session.extra_seconds.get(role, 0.0) + points * SECONDS_PER_POINT
    return bank_seconds(session, role)


# ───────────────────────────── Sprint 4: motor del Rosco ─────────────────────────────

# Material didáctico: `RoscoGame` es la máquina (turno global + estado por jugador) que muta el
# SÓLO el backend; los routers validan permisos/fase y después llaman a `answer`/`timeout`, que
# devuelven un `RoscoOutcome`/`TimeoutOutcome` para que el endpoint sepa si la partida acabó.


@dataclass(frozen=True)
class RoscoQuestion:
    letter: str
    text: str
    answer: str  # forma canónica comparada vía normalize_answer (Regla 5)
    category: str


@dataclass
class RoscoPlayer:
    time_remaining: float = 0.0
    letters: dict[str, LetterStatus] = field(default_factory=dict)
    # Regla 2 (puntero circular): posición actual en el abecedario A-Z (0=A … 25=Z). Avanza tras
    # cada respuesta (acierto/fallo/pasapalabra) saltando las letras ya resueltas; al dar una
    # vuelta completa sin pendientes, el jugador queda `completed`.
    current_letter_index: int = 0
    completed: bool = False


@dataclass
class RoscoGame:
    questions: dict[str, RoscoQuestion] = field(default_factory=dict)
    current_turn: Role | None = "host"  # None = nadie puede jugar (partida acabada)
    players: dict[Role, RoscoPlayer] = field(default_factory=dict)
    ended: bool = False
    winner: Role | None = None
    draw: bool = False


@dataclass
class RoscoOutcome:
    letter: str
    result: LetterStatus  # 'success' | 'failed' | 'pending' (pasapalabra)
    turn_passed: bool
    ended: bool = False
    winner: Role | None = None
    draw: bool = False


@dataclass
class TimeoutOutcome:
    role: Role
    ended: bool
    winner: Role | None = None
    draw: bool = False


def start_rosco(session: LiveSession, question_rows: list[dict]) -> RoscoGame:
    """Arranca el Rosco sobre las filas de `rosco_questions`, con los bancos INDIVIDUALES.

    Normaliza cada respuesta canónica (Regla 5) en el momento de cargar, de modo que luego la
    comparación del jugador es un match exacto contra `normalize_answer`. El host empieza en
    el turno (misma convención que el Draft). Devuelve el motor y lo deja en `session.rosco`.
    """
    questions: dict[str, RoscoQuestion] = {}
    for row in question_rows:
        letter = str(row["letter"]).strip().upper()
        questions[letter] = RoscoQuestion(
            letter=letter,
            text=row["question_text"],
            answer=normalize_answer(row["answer"]),
            category=str(row.get("category", "")),
        )
    game = RoscoGame(
        questions=questions,
        players={
            role: RoscoPlayer(
                time_remaining=bank_seconds(session, role),
                letters={letter: "pending" for letter in questions},
            )
            for role in ("host", "guest")
        },
    )
    session.rosco = game
    return game


def success_count(game: RoscoGame, role: Role) -> int:
    return sum(1 for state in game.players[role].letters.values() if state == "success")


def pending_letters(game: RoscoGame, role: Role) -> list[str]:
    return [letter for letter, state in game.players[role].letters.items() if state == "pending"]


def current_letter(player: RoscoPlayer) -> str | None:
    """Letra activa del puntero circular (None si el jugador ya completó sus 26 letras)."""
    if player.completed:
        return None
    return ROSCO_LETTERS[player.current_letter_index % len(ROSCO_LETTERS)]


def advance_to_next_pending(player: RoscoPlayer) -> bool:
    """Regla 2 (puntero circular): mueve el puntero a la siguiente letra `pending`.

    Incrementa `current_letter_index` (módulo 26) y salta las letras ya resueltas. Da una vuelta
    entera como máximo: si las 26 letras dejan de estar pendientes, marca al jugador como
    `completed` y devuelve `False`. Devuelve `True` si encontró una letra pendiente.
    """
    total = len(ROSCO_LETTERS)
    checked = 0
    while checked < total:
        player.current_letter_index = (player.current_letter_index + 1) % total
        checked += 1
        if player.letters.get(ROSCO_LETTERS[player.current_letter_index]) == "pending":
            return True
    player.completed = True
    return False


def can_play(game: RoscoGame, role: Role) -> bool:
    """¿`role` puede seguir jugando? Solo si le queda tiempo Y alguna letra pendiente."""
    player = game.players[role]
    return (
        player.time_remaining > 0
        and not player.completed
        and any(state == "pending" for state in player.letters.values())
    )


def _other(role: Role) -> Role:
    return "guest" if role == "host" else "host"


def _transfer_turn(game: RoscoGame, first: Role) -> None:
    """Da el turno a `first` si puede jugar; si no a su rival; si ninguno, la partida acaba.

    Es la Regla 2 llevada al límite: al fallar/pasar el turno va al rival, pero si el rival ya
    agotó su tiempo o sus letras, el jugador con vida CONTINÚA en solitario (nadie merece
    quedarse sin jugar porque al otro le hayan cortado el reloj).
    """
    if can_play(game, first):
        game.current_turn = first
        return
    if can_play(game, _other(first)):
        game.current_turn = _other(first)
        return
    _finish(game)


def answer(
    game: RoscoGame,
    role: Role,
    letter: str,
    raw_answer: str,
    time_left: float | None = None,
) -> RoscoOutcome:
    """Resuelve la pregunta de `letter` de `role` y aplica la Regla 2 al turno.

    `raw_answer` vacío o 'pasapalabra' deja la letra `pending` (se podrá reintentar cuando el
    turno vuelva) y pasa el turno. Acierto → `success` y se mantiene el turno; fallo →
    `failed` y se pasa el turno. `time_left` (opcional, reloj del cliente) se guarda como el
    tiempo restante real, que alimenta el desempate de la Regla 4.
    """
    player = game.players[role]
    if time_left is not None:
        player.time_remaining = max(0.0, float(time_left))

    canonical = normalize_answer(raw_answer)
    outcome = RoscoOutcome(letter=letter, result="pending", turn_passed=False)

    if not raw_answer.strip() or canonical == "pasapalabra":
        # Pasapalabra: la letra sigue pendiente y el turno cambia (Regla 2).
        pass
    elif canonical == game.questions[letter].answer.lower():
        # `canonical` ya viene en minúsculas (normalize_answer); `.lower()` sobre la respuesta
        # canónica de la BD blinda la comparación ante cualquier mayúscula persistida.
        # "nasus" == "Nasus" (Regla 5).
        player.letters[letter] = "success"
        outcome.result = "success"
    else:
        player.letters[letter] = "failed"
        outcome.result = "failed"

    # Regla 2 (puntero circular): tras resolver (o pasar) la letra, el puntero avanza a la
    # siguiente pendiente. En un pasapalabra la letra queda `pending` y se revisitará al
    # completar la vuelta, en vez de repetirse de inmediato al recuperar el turno.
    advance_to_next_pending(player)

    if outcome.result == "success" and can_play(game, role):
        game.current_turn = role  # acierto = mantiene el turno (Regla 2)
    else:
        _transfer_turn(game, _other(role))

    outcome.turn_passed = game.current_turn is None or game.current_turn != role
    outcome.ended = game.ended
    outcome.winner = game.winner
    outcome.draw = game.draw
    return outcome


def timeout(game: RoscoGame, role: Role) -> TimeoutOutcome:
    """Un jugador agotó su tiempo: se congela a 0, termina su participación y pasa el turno.

    Solo puede agotarse el reloj del jugador EN TURNO (los relojes se congelan al pasar el
    turno, Regla 2); el router valida ese pre-requisito. Si el rival tampoco puede jugar, la
    partida se da por acabada (Regla 4).
    """
    game.players[role].time_remaining = 0.0
    # El jugador que agota el reloj queda fuera de combate: el turno pasa AL RIVAL
    # incondicionalmente si aún puede jugar (tiempo > 0 y letras pendientes); si el rival ya
    # estaba fuera, se cierra la partida por la Regla 4. Esta comprobación explícita evita el
    # deadlock de esperar un segundo timeout que nunca llega.
    rival = _other(role)
    if can_play(game, rival):
        game.current_turn = rival
    else:
        _finish(game)
    return TimeoutOutcome(role=role, ended=game.ended, winner=game.winner, draw=game.draw)


def _finish(game: RoscoGame) -> None:
    """Cierra la partida aplicando la Regla 4 (tiebreaker).

    Desempate en orden: 1º mayor número de letras acertadas, 2º más tiempo restante,
    3º empate (`draw=True`, sin ganador). Al terminar nadie tiene turno.
    """
    game.ended = True
    game.current_turn = None
    host = game.players["host"]
    guest = game.players["guest"]
    host_hits = success_count(game, "host")
    guest_hits = success_count(game, "guest")
    if host_hits != guest_hits:
        game.winner = "host" if host_hits > guest_hits else "guest"
    elif host.time_remaining != guest.time_remaining:
        game.winner = "host" if host.time_remaining > guest.time_remaining else "guest"
    else:
        game.draw = True