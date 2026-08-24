"""Tests del rating universal calculado en backend (`calculate_participant_rating`) y de la
extracción de participantes que alimenta el JSONB `matches.participants`.
"""

from __future__ import annotations

from backend.app.services.riot import RiotService


def _participant(**overrides) -> dict:
    base = {
        "champion_name": "Jax",
        "puuid": "puuid-1",
        "player_name": "Lucho#EUW",
        "kills": 4,
        "deaths": 2,
        "assists": 6,
        "cs": 200,
        "items": [1, 2, 3, 4, 5, 6, 3340],
        "summoner_spells": [4, 12],
        "team_id": 100,
        "team_position": "TOP",
        "win": True,
        "total_damage": 15000,
        "total_damage_taken": 9000,
        "gold_earned": 12000,
        "vision_score": 25,
        "kill_participation": 0.55,
    }
    base.update(overrides)
    return base


def test_rating_partida_equilibrada():
    """TOP: 4/2/6, 6.67 CS/min (target 7.5), 55% KP (target 0.55), 500 DPM (target 600), victoria
    -> 50 +15(win) +15(kda) -2.5(cs) +0(kp) -2(dpm)."""
    rating = RiotService.calculate_participant_rating(_participant(), 30)
    assert rating == 75.5


def test_rating_partida_perfecta_se_clampa_en_100():
    rating = RiotService.calculate_participant_rating(
        _participant(kills=20, deaths=0, assists=10, cs=300, kill_participation=1.0,
                     total_damage=45000),
        30,
    )
    assert rating == 100.0


def test_rating_int_feed_se_clampa_en_0():
    rating = RiotService.calculate_participant_rating(
        _participant(win=False, kills=0, deaths=15, assists=1, cs=80,
                     kill_participation=0.02, total_damage=3000),
        30,
    )
    assert rating == 0.0


def test_rating_tolera_muertes_cero_y_duracion_invalida():
    """deaths=0 no puede dividir por cero y una duración <= 0 se trata como 1 minuto."""
    rating = RiotService.calculate_participant_rating(_participant(deaths=0), 0)
    assert 0.0 <= rating <= 100.0


def test_rating_soporte_puntua_vision_y_kp_pese_a_cs_bajo():
    """UTILITY: 2/4/18, 1.14 CS/min (target 1.25), 75% KP (peso x30), 343 DPM (target 250),
    visión/min 1.2 (target 1.0), victoria -> 80.0. El mismo statline en TOP sería un desastre;
    en soporte es una buena partida."""
    rating = RiotService.calculate_participant_rating(
        _participant(team_position="UTILITY", kills=2, deaths=4, assists=18, cs=40,
                     kill_participation=0.75, total_damage=12000, vision_score=42),
        35,
    )
    assert rating == 80.0


def test_rating_jungla_target_cs_medio():
    """JUNGLE: 8/5/12, 5.63 CS/min (target 5.75), 72% KP (peso x30), 500 DPM (target 500),
    visión/min 0.5 (target 0.5), derrota -> 35.2."""
    rating = RiotService.calculate_participant_rating(
        _participant(team_position="JUNGLE", kills=8, deaths=5, assists=12, cs=180,
                     kill_participation=0.72, total_damage=16000, vision_score=16, win=False),
        32,
    )
    assert rating == 35.2


def test_rating_posicion_desconocida_usa_perfil_neutro():
    """Sin posición (ARAM/remake): perfil heredado de la fórmula original.
    1/2/3 (KDA 2), 7.0 CS/min, 50% KP, 550 DPM, victoria -> 65.0."""
    rating = RiotService.calculate_participant_rating(
        _participant(team_position="", kills=1, deaths=2, assists=3, cs=210,
                     kill_participation=0.5, total_damage=16500),
        30,
    )
    assert rating == 65.0


def test_extract_participants_formato_completo():
    raw = [
        {"riotIdGameName": "Lucho", "riotIdTagline": "EUW", "puuid": "p1", "championName": "Jax",
         "summonerName": "viejo_nombre", "kills": 5, "deaths": 2, "assists": 2,
         "totalMinionsKilled": 180, "neutralMinionsKilled": 20, "item0": 1, "item5": 6,
         "item6": 3340, "summoner1Id": 4, "summoner2Id": 12, "teamId": 100,
         "teamPosition": "TOP", "win": True, "totalDamageDealtToChampions": 21000},
        {"riotIdGameName": "Mate", "riotIdTagline": "EUW", "puuid": "p2", "championName": "Lee Sin",
         "summonerName": "otro", "kills": 3, "deaths": 4, "assists": 8,
         "totalMinionsKilled": 40, "neutralMinionsKilled": 60, "teamId": 100,
         "teamPosition": "JUNGLE", "win": True, "totalDamageDealtToChampions": 12000},
        {"riotIdGameName": "", "riotIdTagline": "", "puuid": "p3", "championName": "Annie",
         "summonerName": "bot_legacy", "kills": 0, "deaths": 5, "assists": 1,
         "totalMinionsKilled": 30, "neutralMinionsKilled": 0, "teamId": 200,
         "teamPosition": "MIDDLE", "win": False, "totalDamageDealtToChampions": 4000},
    ]

    participants = RiotService._extract_participants(raw, 32)

    assert len(participants) == 3

    lucho = participants[0]
    assert lucho["player_name"] == "Lucho#EUW"
    assert len(lucho["items"]) == 7
    assert lucho["items"][6] == 3340          # trinket en el slot 6
    assert lucho["cs"] == 200                 # minions + neutrales
    assert lucho["total_damage"] == 21000
    # KP del equipo 100: (5+2) / (5+3) kills totales
    assert lucho["kill_participation"] == 0.875
    assert 0.0 <= lucho["rating"] <= 100.0
    # Trazabilidad: todo participante recién sincronizado lleva el sello de versión.
    assert lucho["rating_version"] == 1

    bot = participants[2]
    assert bot["player_name"] == "bot_legacy"  # sin Riot ID, cae al summonerName
    assert bot["kill_participation"] == 0.0    # nadie más en su equipo mató
