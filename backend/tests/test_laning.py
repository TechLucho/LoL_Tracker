"""Unidad del Triángulo del Laning: del Timeline de Riot a GD@15/XPD@15/CSD@15.

`_extract_laning_deltas` es estática y pura (sin red, sin DB): el test construye el
informe de una partida y su timeline a mano y verifica el frame elegido y los deltas.
"""

from __future__ import annotations

from typing import Any

from backend.app.services.riot import RiotService


def _info(duration_s: int = 1320) -> dict[str, Any]:
    return {
        "gameDuration": duration_s,
        "participants": [
            {
                "participantId": 1, "puuid": "me", "teamId": 100,
                "teamPosition": "MIDDLE", "championName": "Ahri",
            },
            {
                "participantId": 2, "puuid": "ally", "teamId": 100,
                "teamPosition": "TOP", "championName": "Gnar",
            },
            {
                "participantId": 4, "puuid": "enemy", "teamId": 200,
                "teamPosition": "MIDDLE", "championName": "Syndra",
            },
            {
                "participantId": 5, "puuid": "enemy_top", "teamId": 200,
                "teamPosition": "TOP", "championName": "Ornn",
            },
        ],
    }


def _me(info: dict[str, Any]) -> dict[str, Any]:
    return next(p for p in info["participants"] if p["puuid"] == "me")


def _stats(gold: int, xp: int, cs: int, jungle: int = 0) -> dict[str, int]:
    return {
        "totalGold": gold,
        "xp": xp,
        "minionsKilled": cs,
        "jungleMinionsKilled": jungle,
    }


def _frame(ts: int, stats: dict[int, dict[str, int]]) -> dict[str, Any]:
    return {"timestamp": ts, "participantFrames": {str(k): v for k, v in stats.items()}}


def test_elige_el_frame_mas_cercano_a_15min_y_resta_al_rival():
    timeline = {
        "info": {
            "frames": [
                _frame(800_000, {1: _stats(3500, 2500, 40), 4: _stats(3400, 2450, 38)}),
                _frame(900_000, {1: _stats(4500, 3200, 46), 4: _stats(4200, 3000, 43)}),
                _frame(985_000, {1: _stats(5100, 3400, 50), 4: _stats(4700, 3300, 47)}),
            ]
        }
    }
    deltas = RiotService._extract_laning_deltas(_info(), _me(_info()), timeline)

    # El frame de 900.000 ms es el más cercano al minuto 15: oro +300, xp +200, cs 46-43=+3.
    assert deltas == {"gd15": 300.0, "xpd15": 200.0, "csd15": 3}


def test_contabiliza_cs_de_jungla():
    timeline = {
        "info": {
            "frames": [
                _frame(
                    900_000,
                    {
                        1: _stats(4500, 3200, 45, jungle=3),   # 48 CS para el usuario
                        4: _stats(4200, 3000, 40, jungle=10),  # 50 CS para el rival
                    },
                )
            ]
        }
    }
    deltas = RiotService._extract_laning_deltas(_info(), _me(_info()), timeline)
    assert deltas["csd15"] == -2


def test_partida_menor_de_15min_no_genera_laning():
    timeline = {
        "info": {
            "frames": [
                _frame(700_000, {1: _stats(3000, 2000, 30), 4: _stats(2900, 1950, 29)}),
            ]
        }
    }
    assert RiotService._extract_laning_deltas(_info(duration_s=700), _me(_info()), timeline) is None


def test_sin_rival_con_mismo_rol_no_genera_laning():
    # El rival de MIDDLE juega TOP: no hay oponente directo de línea.
    info = _info()
    info["participants"][2]["teamPosition"] = "TOP"
    timeline = {"info": {"frames": [_frame(900_000, {1: _stats(4500, 3200, 46), 4: _stats(4200, 3000, 43)})]}}
    assert RiotService._extract_laning_deltas(info, _me(info), timeline) is None


def test_sin_frame_del_rival_no_genera_laning():
    # Falta el participante 4 en el frame: no se puede comparar, mejor no inventar nada.
    timeline = {"info": {"frames": [_frame(900_000, {1: _stats(4500, 3200, 46)})]}}
    assert RiotService._extract_laning_deltas(_info(), _me(_info()), timeline) is None