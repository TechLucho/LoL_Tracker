"""El Rosco (Sprint 4): motor en memoria, turnos y fin de partida (Reglas 2, 4 y 5).

Herméticos: sin DB real ni red. Se monkeypatchean `repositories.games` (incluido el nuevo
`get_rosco_questions`/`finish_game`) y `realtime_bus`; el motor (`services/live_game.rosco`)
sí es el real, que es justo lo que cubren los tests de la lógica de turnos.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories import games as repo
from backend.app.services import live_game
from backend.app.services import realtime_bus
from backend.tests.conftest import TEST_USER_UUID, make_auth_headers

GUEST_UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")
OUTSIDER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000003")

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _fake_questions() -> list[dict]:
    """Las 26 preguntas como las devolvería `rosco_questions` (M = "Master Yi" para probar Regla 5)."""
    rows = [
        {
            "letter": ch,
            "question_text": f"¿Qué campeón empieza por la letra {ch}?",
            "answer": f"Campeon{ch}",  # normalize → "campeonX"
            "category": "Lore",
        }
        for ch in _LETTERS
    ]
    rows[_LETTERS.index("M")]["answer"] = "Master Yi"
    return rows


def _correct_answer(letter: str) -> str:
    return "Master Yi" if letter == "M" else f"Campeon{letter}"


def _new_game() -> tuple[live_game.LiveSession, live_game.RoscoGame]:
    session = live_game.LiveSession()
    return session, live_game.start_rosco(session, _fake_questions())


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fake_bus(monkeypatch):
    """Captura los broadcasts en `calls` para no tocar Supabase Realtime."""
    calls: list[tuple[str, str, dict]] = []

    async def _fake_broadcast(code: str, event: str, payload: dict) -> bool:
        calls.append((code, event, payload))
        return True

    monkeypatch.setattr(realtime_bus, "broadcast", _fake_broadcast)
    yield {"calls": calls}


def _make_room(status: str, code: str, guest_id: uuid.UUID | None = GUEST_UUID) -> dict:
    return {
        "id": uuid.uuid4(),
        "room_code": code,
        "host_id": TEST_USER_UUID,
        "guest_id": guest_id,
        "status": status,
        "created_at": None,
        "winner_id": None,
    }


@pytest.fixture
def games(monkeypatch):
    """DB falsa de una sala con el banco de preguntas y el cierre de partida."""
    store: dict[str, dict] = {}
    finishes: list[tuple[str, object]] = []

    async def get_room_by_code(code: str) -> dict | None:
        return dict(store[code]) if code in store else None

    async def update_status(code: str, new: str, expected: str) -> dict | None:
        room = store.get(code)
        if room is None or room["status"] != expected:
            return None
        room = dict(room)
        room["status"] = new
        store[code] = room
        return room

    async def get_rosco_questions() -> list[dict]:
        return _fake_questions()

    async def finish_game(code: str, winner_id) -> dict | None:
        room = store.get(code)
        if room is None or room["status"] != "rosco":
            return None
        room = dict(room)
        room["status"] = "finished"
        room["winner_id"] = winner_id
        store[code] = room
        finishes.append((code, winner_id))
        return room

    monkeypatch.setattr(repo, "get_room_by_code", get_room_by_code)
    monkeypatch.setattr(repo, "update_status", update_status)
    monkeypatch.setattr(repo, "get_rosco_questions", get_rosco_questions)
    monkeypatch.setattr(repo, "finish_game", finish_game)

    def spawn(code: str, status: str = "rosco", guest_id: uuid.UUID | None = GUEST_UUID):
        room = _make_room(status, code, guest_id=guest_id)
        store[code] = room
        live_game.drop_session(code)
        session = live_game.ensure_session(code)
        live_game.start_rosco(session, _fake_questions())
        return session

    spawn.__dict__["store"] = store
    spawn.__dict__["finishes"] = finishes
    return spawn


def _headers(sub=TEST_USER_UUID) -> dict:
    return make_auth_headers(sub)


# ───────────────────────────── unit: motor del Rosco ─────────────────────────────


def test_rosco_arranca_con_26_pendientes_turno_host_y_bancos_individuales():
    session = live_game.LiveSession()
    live_game.add_score(session, "guest", 5)  # el guest gana 5s en minijuegos (Regla 3)
    game = live_game.start_rosco(session, _fake_questions())
    assert game.current_turn == "host"
    assert len(game.questions) == 26
    assert live_game.pending_letters(game, "host") == list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert live_game.success_count(game, "host") == 0
    assert game.players["host"].time_remaining == 100.0
    assert game.players["guest"].time_remaining == 105.0
    assert session.rosco is game


def test_acierto_mantiene_el_turno():
    _, game = _new_game()
    outcome = live_game.answer(game, "host", "A", "CampeonA")
    assert outcome.result == "success"
    assert not outcome.turn_passed
    assert outcome.ended is False
    assert game.current_turn == "host"
    assert game.players["host"].letters["A"] == "success"


def test_fallo_pasa_el_turno_y_marca_letra_fallada():
    _, game = _new_game()
    outcome = live_game.answer(game, "host", "B", "Respuesta incorrecta")
    assert outcome.result == "failed"
    assert outcome.turn_passed
    assert game.current_turn == "guest"
    assert game.players["host"].letters["B"] == "failed"


def test_pasapalabra_conserva_pending_y_se_reintenta_al_volver_el_turno():
    _, game = _new_game()
    outcome = live_game.answer(game, "host", "C", "pasapalabra")
    assert outcome.result == "pending"
    assert outcome.turn_passed
    assert game.players["host"].letters["C"] == "pending"  # no se quema la letra
    assert game.current_turn == "guest"

    live_game.answer(game, "guest", "C", "Equivocado")  # el guest falla → vuelve el host
    assert game.current_turn == "host"
    outcome = live_game.answer(game, "host", "C", "CampeonC")
    assert outcome.result == "success"
    assert game.players["host"].letters["C"] == "success"


def test_respuestas_se_normalizan_antes_de_comparar():
    _, game = _new_game()
    # "Master Yi" acertaría solo con el normalizador (Regla 5): pegada y en minúsculas.
    outcome = live_game.answer(game, "host", "M", "  master   YI ")
    assert outcome.result == "success"
    # Y una respuesta parecida pero distinta NO puede colar.
    outcome = live_game.answer(game, "host", "M", "Master Yi Is Here")
    assert outcome.result == "failed"


def test_regla_4_desempata_por_aciertos():
    _, game = _new_game()
    live_game.answer(game, "host", "A", "CampeonA")   # host 1 acierto
    live_game.answer(game, "host", "B", "CampeonB")   # host 2 aciertos
    live_game.answer(game, "host", "C", "")           # host pasa → turno del guest
    live_game.answer(game, "guest", "D", "CampeonD")  # guest 1 acierto

    assert not live_game.timeout(game, "guest").ended  # guest fuera, host sigue
    outcome = live_game.timeout(game, "host")
    assert outcome.ended
    assert outcome.winner == "host"  # 2 aciertos > 1


def test_regla_4_desempata_por_tiempo_restante():
    _, game = _new_game()
    # Ambos resuelven las 26 letras: el host lo hace conservando más tiempo → gana por el 2º
    # criterio de la Regla 4 (empate a 26 aciertos).
    for letter in _LETTERS:
        live_game.answer(game, "host", letter, _correct_answer(letter), time_left=60.0)
    assert game.current_turn == "guest"  # el host ya terminó; juega el guest en solitario
    for letter in _LETTERS:
        live_game.answer(game, "guest", letter, _correct_answer(letter), time_left=40.0)

    assert game.ended
    assert game.winner == "host"  # 26-26 en aciertos, 60s vs 40s en tiempo


def test_regla_4_termina_en_empate():
    _, game = _new_game()
    live_game.answer(game, "host", "A", "CampeonA", time_left=30.0)   # host 1 acierto
    live_game.answer(game, "host", "B", "Mal", time_left=30.0)        # falla → turno guest
    live_game.answer(game, "guest", "C", "CampeonC", time_left=30.0)  # guest 1 acierto

    live_game.timeout(game, "guest")
    outcome = live_game.timeout(game, "host")
    assert outcome.ended
    assert outcome.winner is None
    assert outcome.draw  # 1-1 en aciertos y mismo tiempo → empate (Regla 4, 3º criterio)


def test_quien_resuelve_todas_sus_letras_sigue_solo_y_gana():
    _, game = _new_game()
    # El host acierta las 26 letras seguidas (Regla 2: el acierto mantiene el turno).
    for letter in _LETTERS:
        live_game.answer(game, "host", letter, _correct_answer(letter))
    assert not game.ended
    assert game.current_turn == "guest"  # el host ya no tiene letras: juega el guest

    # El guest falla una letra (A) y acierta el resto: el host nunca recupera el turno.
    live_game.answer(game, "guest", "A", "Equivocado")
    assert game.current_turn == "guest"
    assert not game.ended
    for letter in _LETTERS[1:]:
        live_game.answer(game, "guest", letter, _correct_answer(letter))

    assert game.ended
    assert game.winner == "host"  # 26 aciertos vs 25 (Regla 4)


# ───────────────────────────── endpoints: answer ─────────────────────────────


def test_answer_fuera_de_la_fase_rosco_se_rechaza(client, games, _fake_bus):
    games("NOPASE", status="minigames")
    r = client.post("/api/games/rooms/NOPASE/rosco/answer",
                    json={"letter": "A", "answer": "CampeonA"}, headers=_headers())
    assert r.status_code == 400
    assert "fase" in r.json()["detail"]


def test_answer_para_no_miembros_se_rechaza(client, games, _fake_bus):
    games("ALIENA")
    r = client.post("/api/games/rooms/ALIENA/rosco/answer",
                    json={"letter": "A", "answer": "CampeonA"}, headers=_headers(OUTSIDER_UUID))
    assert r.status_code == 400
    assert "No estás" in r.json()["detail"]


def test_answer_respeta_el_turno_y_la_letra_pendiente(client, games, _fake_bus):
    games("NOTURN")
    # El guest intenta robar el turno del host.
    r = client.post("/api/games/rooms/NOTURN/rosco/answer",
                    json={"letter": "A", "answer": "CampeonA"}, headers=_headers(GUEST_UUID))
    assert r.status_code == 400
    assert "turno" in r.json()["detail"].lower()
    # Una letra ya resuelta no se puede volver a responder.
    games("REHELA")
    client.post("/api/games/rooms/REHELA/rosco/answer",
                json={"letter": "A", "answer": "CampeonA"}, headers=_headers())
    r = client.post("/api/games/rooms/REHELA/rosco/answer",
                    json={"letter": "A", "answer": "CampeonA"}, headers=_headers())
    assert r.status_code == 400
    assert "resuelta" in r.json()["detail"].lower()


def test_answer_acierto_mantiene_el_turno_y_difunde(client, games, _fake_bus):
    games("ACIERT")
    r = client.post("/api/games/rooms/ACIERT/rosco/answer",
                    json={"letter": "A", "answer": "CampeonA"}, headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rosco"
    assert body["current_turn"] == "host"  # acierto = sigue el turno (Regla 2)
    assert body["players"]["host"]["letters"][0]["letter"] == "A"
    assert body["players"]["host"]["letters"][0]["status"] == "success"
    assert (_fake_bus["calls"][-1][0], _fake_bus["calls"][-1][1]) == ("ACIERT", "rosco")


def test_answer_que_acaba_la_partida_persiste_ganador_y_emite_game_over(
    client, games, _fake_bus,
):
    session = games("FINROS")
    game = session.rosco
    # Estado casi final: host con 25 de 26 (solo Z), guest sin tiempo (ya quedó fuera).
    for letter in _LETTERS[:-1]:
        game.players["host"].letters[letter] = "success"
    game.players["guest"].time_remaining = 0.0

    r = client.post("/api/games/rooms/FINROS/rosco/answer",
                    json={"letter": "Z", "answer": "CampeonZ", "time_remaining": 30.0},
                    headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "finished"
    assert body["current_turn"] is None
    assert body["winner"] == "host"
    assert body["draw"] is False
    # El ganador se persiste en game_rooms (winner_id = host) y el evento es game_over.
    assert games.finishes[-1] == ("FINROS", TEST_USER_UUID)
    assert _fake_bus["calls"][-1][1] == "game_over"


# ───────────────────────────── endpoints: timeout ─────────────────────────────


def test_timeout_solo_puede_expirar_quien_esta_en_turno(client, games, _fake_bus):
    games("CRONOS")
    r = client.post("/api/games/rooms/CRONOS/rosco/timeout", headers=_headers(GUEST_UUID))
    assert r.status_code == 400
    assert "no es tu turno" in r.json()["detail"].lower()


def test_timeout_pasa_el_turno_y_el_fin_emite_game_over_con_empate(client, games, _fake_bus):
    games("TIMEOU")
    r = client.post("/api/games/rooms/TIMEOU/rosco/timeout", headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rosco"
    assert body["current_turn"] == "guest"  # el host se queda a 0 y rota
    assert body["players"]["host"]["time_remaining"] == 0.0

    r2 = client.post("/api/games/rooms/TIMEOU/rosco/timeout", headers=_headers(GUEST_UUID))
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "finished"
    assert body["winner"] is None
    assert body["draw"] is True  # sin aciertos y ambos a 0 → empate (Regla 4)
    assert games.finishes[-1] == ("TIMEOU", None)
    assert _fake_bus["calls"][-1][1] == "game_over"


# ───────────────────────────── endpoints: transición al rosco ─────────────────────────────


def test_transicion_a_rosco_carga_preguntas_y_difunde_el_rosco(client, games, _fake_bus):
    session = games("KOMENZ", status="minigames")
    session.draft_picks = {"host": "Lore", "guest": "Mecánicas"}  # draft completo
    r = client.post("/api/games/rooms/KOMENZ/state", json={"status": "rosco"},
                    headers=_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "rosco"
    # Tras el contrato de sala se difunde el estado completo del Rosco (turno + letras).
    assert (_fake_bus["calls"][-1][0], _fake_bus["calls"][-1][1]) == ("KOMENZ", "rosco")
    rosco = _fake_bus["calls"][-1][2]
    assert len(rosco["players"]["host"]["letters"]) == 26
    assert rosco["current_turn"] == "host"