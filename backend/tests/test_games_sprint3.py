"""El Rosco (Sprint 3): máquina de estados, draft y banco de tiempo (Regla 3).

Herméticos: sin DB real ni red. Se monkeypatchean `repositories.games` y `realtime_bus`
para que ningún test toque Postgres/Supabase; el estado en vivo sí es el real
(services/live_game), que es justo lo que se quiere cubrir.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories import games as repo
from backend.app.services import live_game
from backend.app.services import realtime_bus
from backend.tests.conftest import TEST_USER_UUID, make_auth_headers

GUEST_UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")
OUTSIDER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000003")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def make_room(status: str, code: str = "AAAAAA", guest_id: uuid.UUID | None = GUEST_UUID) -> dict:
    """Sala sintética tal y como la devolvería game_rooms (host = TEST_USER_UUID)."""
    return {
        "id": uuid.uuid4(),
        "room_code": code,
        "host_id": TEST_USER_UUID,
        "guest_id": guest_id,
        "status": status,
        "created_at": datetime.now(timezone.utc),  # GameRoom lo exige en la respuesta de join
    }


@pytest.fixture(autouse=True)
def _fake_db_and_bus(monkeypatch):
    """Conecta el router a una DB falsa y captura los broadcasts en `calls`."""
    calls: list[tuple[str, str, dict]] = []

    async def _fake_broadcast(code: str, event: str, payload: dict) -> bool:
        calls.append((code, event, payload))
        return True

    monkeypatch.setattr(realtime_bus, "broadcast", _fake_broadcast)
    yield {"calls": calls}


@pytest.fixture
def rooms(monkeypatch):
    """DB falsa de una sala: get_room_by_code sirve el estado mutable; update_status transiciona."""
    store: dict[str, dict] = {}

    async def get_room_by_code(code: str) -> dict | None:
        return dict(store.get(code)) if code in store else None

    async def update_status(code: str, new: str, expected: str) -> dict | None:
        room = store.get(code)
        if room is None or room["status"] != expected:
            return None
        room = dict(room)
        room["status"] = new
        store[code] = room
        return room

    async def find_lobby_by_code(code: str) -> dict | None:
        room = store.get(code)
        return dict(room) if room is not None and room["status"] == "lobby" else None

    async def claim_guest(code: str, guest_id: uuid.UUID) -> dict | None:
        """Misma semántica atómica que repositories/games.py: solo en 'lobby', asiento libre, no-host."""
        room = store.get(code)
        if room is None or room["status"] != "lobby" or room["guest_id"] is not None:
            return None
        if room["host_id"] == guest_id:
            return None
        room = dict(room)
        room["guest_id"] = guest_id
        store[code] = room
        return room

    monkeypatch.setattr(repo, "get_room_by_code", get_room_by_code)
    monkeypatch.setattr(repo, "update_status", update_status)
    monkeypatch.setattr(repo, "find_lobby_by_code", find_lobby_by_code)
    monkeypatch.setattr(repo, "claim_guest", claim_guest)

    def spawn(code: str, status: str = "drafting", guest_id: uuid.UUID | None = GUEST_UUID) -> dict:
        room = make_room(status, code, guest_id=guest_id)
        store[code] = room
        live_game.drop_session(code)  # estado vivo limpio por sala
        return room

    spawn.__dict__["store"] = store
    return spawn


def _headers(sub=TEST_USER_UUID) -> dict:
    return make_auth_headers(sub)


# ───────────────────────────── unit: live_game ─────────────────────────────


def test_banco_base_es_100_sin_partida():
    session = live_game.LiveSession()
    assert live_game.bank_seconds(session, "host") == 100.0
    assert live_game.bank_seconds(session, "guest") == 100.0


def test_add_score_solo_suma_al_banco_del_autor():
    session = live_game.LiveSession()
    assert live_game.add_score(session, "host", 5) == 105.0
    assert live_game.bank_seconds(session, "guest") == 100.0  # el rival no se ve afectado
    assert live_game.add_score(session, "host", 2) == 107.0


def test_draft_se_completa_con_dos_elegidas():
    session = live_game.LiveSession()
    assert session.draft_turn == "host"  # el host elige primero
    assert not session.draft_complete
    live_game.apply_draft_pick(session, "host", "Lore")
    assert session.draft_turn == "guest"
    assert not session.draft_complete
    live_game.apply_draft_pick(session, "guest", "Mecánicas")
    assert session.draft_turn is None
    assert session.draft_complete


# ───────────────────────────── draft ─────────────────────────────


def test_draft_respeta_el_turno_alterno(client, rooms, _fake_db_and_bus):
    rooms("TRAID1")
    # El guest intenta robar el turno del host.
    r = client.post("/api/games/rooms/TRAID1/draft",
                    json={"category": "Lore"}, headers=_headers(GUEST_UUID))
    assert r.status_code == 400

    r = client.post("/api/games/rooms/TRAID1/draft",
                    json={"category": "Lore"}, headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["draft_turn"] == "guest"
    assert body["draft_picks"] == {"host": "Lore"}
    assert body["time_banks"] == {"host": 100.0, "guest": 100.0}


def test_draft_no_permite_categorias_repetidas_ni_invalidas(client, rooms, _fake_db_and_bus):
    rooms("DRAFT2")
    client.post("/api/games/rooms/DRAFT2/draft", json={"category": "Lore"}, headers=_headers())
    # El guest ya no puede repetir la categoría del host.
    r = client.post("/api/games/rooms/DRAFT2/draft",
                    json={"category": "Lore"}, headers=_headers(GUEST_UUID))
    assert r.status_code == 400
    assert "ya la eligió" in r.json()["detail"]
    # Ni una categoría fuera del catálogo.
    r = client.post("/api/games/rooms/DRAFT2/draft",
                    json={"category": "Historia"}, headers=_headers(GUEST_UUID))
    assert r.status_code == 400
    assert "no válida" in r.json()["detail"]


def test_draft_fuera_de_fase_se_rechaza(client, rooms, _fake_db_and_bus):
    rooms("NODRFT", status="minigames")
    r = client.post("/api/games/rooms/NODRFT/draft", json={"category": "Lore"}, headers=_headers())
    assert r.status_code == 400
    assert "drafting" in r.json()["detail"]


def test_draft_para_no_miembros(client, rooms, _fake_db_and_bus):
    rooms("INTREF")
    r = client.post("/api/games/rooms/INTREF/draft",
                    json={"category": "Lore"}, headers=_headers(OUTSIDER_UUID))
    assert r.status_code == 400
    assert "No estás" in r.json()["detail"]


# ───────────────────────────── state ─────────────────────────────


def test_state_no_avanza_sin_invitado_a_drafting(client, rooms, _fake_db_and_bus):
    """lobby → drafting es decisión del host y exige un invitado en la sala (Regla 1)."""
    rooms("NOGUEST", status="lobby", guest_id=None)
    r = client.post("/api/games/rooms/NOGUEST/state", json={"status": "drafting"},
                    headers=_headers())
    assert r.status_code == 400
    assert "invitado" in r.json()["detail"]


def test_state_host_inicia_el_drafting_con_invitado(client, rooms, _fake_db_and_bus):
    """El join ya no consume lobby → drafting; lo dispara el host deliberadamente."""
    rooms("TODRAFT", status="lobby")
    r = client.post("/api/games/rooms/TODRAFT/state", json={"status": "drafting"},
                    headers=_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "drafting"
    assert r.json()["draft_turn"] == "host"
    assert (_fake_db_and_bus["calls"][-1][0], _fake_db_and_bus["calls"][-1][1]) == ("TODRAFT", "state")


def test_state_no_avanza_sin_draft_completo(client, rooms, _fake_db_and_bus):
    rooms("NODONE")
    r = client.post("/api/games/rooms/NODONE/state", json={"status": "minigames"},
                    headers=_headers())
    assert r.status_code == 400
    assert "draft" in r.json()["detail"].lower()


def test_state_avanza_con_draft_completo_y_difunde(client, rooms, _fake_db_and_bus):
    rooms("GONEXT")
    client.post("/api/games/rooms/GONEXT/draft", json={"category": "Lore"}, headers=_headers())
    client.post("/api/games/rooms/GONEXT/draft",
                json={"category": "Mecánicas"}, headers=_headers(GUEST_UUID))
    r = client.post("/api/games/rooms/GONEXT/state", json={"status": "minigames"},
                    headers=_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "minigames"
    assert (_fake_db_and_bus["calls"][-1][0], _fake_db_and_bus["calls"][-1][1]) == ("GONEXT", "state")


def test_state_rechaza_transiciones_ilegales(client, rooms, _fake_db_and_bus):
    rooms("JUMPIT")
    r = client.post("/api/games/rooms/JUMPIT/state", json={"status": "rosco"},
                    headers=_headers())
    assert r.status_code == 400
    assert "permitida" in r.json()["detail"]


def test_state_conflicto_de_carrera_da_409(client, monkeypatch, _fake_db_and_bus):
    """Si otro request movió el estado antes del UPDATE atómico → 409, no 400."""
    store = {"RACITY": make_room("minigames", "RACITY")}

    async def get_room_by_code(code: str) -> dict | None:
        return dict(store[code])

    async def update_status(code: str, new: str, expected: str) -> dict | None:
        return None  # simula que otro jugador cambió el estado entremedidas

    monkeypatch.setattr(repo, "get_room_by_code", get_room_by_code)
    monkeypatch.setattr(repo, "update_status", update_status)
    r = client.post("/api/games/rooms/RACITY/state", json={"status": "rosco"},
                    headers=_headers())
    assert r.status_code == 409


# ───────────────────────────── score (Regla 3) ─────────────────────────────


def test_score_fuera_de_minigames_se_rechaza(client, rooms, _fake_db_and_bus):
    rooms("NOMINI", status="drafting")
    r = client.post("/api/games/rooms/NOMINI/score", json={"points": 3}, headers=_headers())
    assert r.status_code == 400


def test_score_acumula_segundos_en_el_banco_individual(client, rooms, _fake_db_and_bus):
    rooms("SCORER", status="minigames")
    r = client.post("/api/games/rooms/SCORER/score", json={"points": 3}, headers=_headers())
    assert r.status_code == 200
    assert r.json()["time_banks"]["host"] == 103.0
    assert r.json()["time_banks"]["guest"] == 100.0

    r2 = client.post("/api/games/rooms/SCORER/score", json={"points": 2}, headers=_headers(GUEST_UUID))
    assert r2.json()["time_banks"]["guest"] == 102.0
    assert r2.json()["time_banks"]["host"] == 103.0  # el host conserva lo suyo (Regla 3)


def test_score_valida_puntos_repartidos_por_pydantic(client, rooms, _fake_db_and_bus):
    rooms("LIMITS", status="minigames")
    for puntos in (0, 101, -5):
        r = client.post("/api/games/rooms/LIMITS/score", json={"points": puntos},
                        headers=_headers())
        assert r.status_code == 422, f"points={puntos} debería ser rechazado"


def test_score_no_miembro(client, rooms, _fake_db_and_bus):
    rooms("ALIENN", status="minigames")
    r = client.post("/api/games/rooms/ALIENN/score", json={"points": 3},
                    headers=_headers(OUTSIDER_UUID))
    assert r.status_code == 400


# ───────────────────────────── join / rejoin (Regla 1) ─────────────────────────────


def test_join_asigna_el_asiento_de_invitado_en_lobby(client, rooms, _fake_db_and_bus):
    """Un usuario nuevo ocupa el asiento libre en 'lobby' y se difunde el estado de sala."""
    rooms("JOINUP", status="lobby", guest_id=None)
    r = client.post("/api/games/rooms/JOINUP/join", headers=_headers(GUEST_UUID))
    assert r.status_code == 200
    body = r.json()
    assert body["guest_id"] == str(GUEST_UUID)
    assert body["status"] == "lobby"
    assert (_fake_db_and_bus["calls"][-1][0], _fake_db_and_bus["calls"][-1][1]) == ("JOINUP", "state")


def test_join_no_deja_entrar_a_un_nuevo_invitado_fuera_de_lobby(client, rooms, _fake_db_and_bus):
    """Un no-miembro no puede colarse en una partida ya empezada: solo hay rejoin para miembros."""
    rooms("PLYNG1", status="minigames")
    r = client.post("/api/games/rooms/PLYNG1/join", headers=_headers(OUTSIDER_UUID))
    assert r.status_code == 400
    assert "empezado" in r.json()["detail"]


def test_join_no_deja_entrar_a_un_nuevo_invitado_con_asiento_ocupado(client, rooms, _fake_db_and_bus):
    """En 'lobby' el asiento de invitado es único: un segundo invitado es rechazado."""
    rooms("OCCUPD", status="lobby", guest_id=GUEST_UUID)
    r = client.post("/api/games/rooms/OCCUPD/join", headers=_headers(OUTSIDER_UUID))
    assert r.status_code == 400
    assert "invitado" in r.json()["detail"]


def test_rejoin_del_host_devuelve_la_sala_en_cualquier_fase(client, rooms, _fake_db_and_bus):
    """El host reconecta a mitad de partida y recibe la sala con 200 para re-suscribirse."""
    rooms("RECONH", status="rosco")
    r = client.post("/api/games/rooms/RECONH/join", headers=_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "rosco"
    assert (_fake_db_and_bus["calls"][-1][0], _fake_db_and_bus["calls"][-1][1]) == ("RECONH", "state")


def test_rejoin_del_guest_devuelve_la_sala_acabada(client, rooms, _fake_db_and_bus):
    """El invitado reconecta cuando la partida ya terminó: recibe la sala 'finished' (200)."""
    rooms("FINLAP", status="finished")
    r = client.post("/api/games/rooms/FINLAP/join", headers=_headers(GUEST_UUID))
    assert r.status_code == 200
    assert r.json()["status"] == "finished"


def test_join_de_sala_inexistente_da_400(client, rooms, _fake_db_and_bus):
    r = client.post("/api/games/rooms/NOPE01/join", headers=_headers(GUEST_UUID))
    assert r.status_code == 400
    assert "no existe" in r.json()["detail"]