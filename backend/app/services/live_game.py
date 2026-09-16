"""El Rosco — estado vivo de la partida en memoria (Sprint 3).

Sigue la Regla 1 de CHECKLIST: el backend es el árbitro y fuente de verdad; la DB
(`game_rooms`) persiste emparejamiento, estado de la máquina y resultado final, pero NO el
estado en vivo. Lo que aquí guardamos por `room_code` es exactamente eso, el estado vivo:

  * `draft_turn`  — a quién le toca elegir categoría ('host' arranca siempre).
  * `draft_picks` — categoría elegida por rol (1 cada uno, de DRAFT_CATEGORIES).
  * `extra_seconds` — segundos ganados por rol en los minijuegos (Regla 3).

MONO-PROCESO: igual que `_SyncState` y las métricas, esto vive en la memoria del proceso.
`main._assert_single_process` ya impide levantar con varios workers; si además el proceso
se reinicia a mitad de una partida, el draft/banco se pierde (los ESTADOS persisten en DB,
el emparejamiento también) — aceptable para el Sprint 3, el Sprint 4 añadirá la máquina de
estados del Rosco con la misma regla.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass
class LiveSession:
    draft_turn: Role | None = "host"  # el host elige primero
    draft_picks: dict[Role, str] = field(default_factory=dict)
    extra_seconds: dict[Role, float] = field(default_factory=dict)

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