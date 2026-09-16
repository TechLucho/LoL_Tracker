"""Tests de las líneas base por rol (`services/baselines.py`).

Garantizan el contrato de la comparativa de Full Stats: los targets espejan el rating
(`_ROLE_PROFILES`) para no contradecir al `calculate_participant_rating`, la KP% va como
ratio 0-1, la visión esperada escala con la duración, y los roles desconocidos caen al
perfil neutro sin romper la serialización.
"""

from __future__ import annotations

from backend.app.services.baselines import (
    DEFAULT_BASELINE,
    ROLE_BASELINES,
    enrich_match_row,
    expected_stats_for,
    baseline_for,
)


def test_soporte_prioriza_vision_y_carriles_cs_dpm():
    """El array cubre los 5 roles: soporte destaca en visión, ADC/carriles en CS/DPM."""
    assert set(ROLE_BASELINES) == {"TOP", "MIDDLE", "BOTTOM", "JUNGLE", "UTILITY"}

    support = ROLE_BASELINES["UTILITY"]
    adc = ROLE_BASELINES["BOTTOM"]

    assert support.vision_per_min == 1.0
    assert support.cs_per_min < adc.cs_per_min
    assert support.dpm < adc.dpm


def test_baselines_espejan_targets_del_rating():
    """CS/min y DPM coinciden con _ROLE_PROFILES de riot.py (decisión: nunca contradecir rating)."""
    expected = {
        "TOP": (7.5, 600),
        "MIDDLE": (7.5, 650),
        "BOTTOM": (7.5, 600),
        "JUNGLE": (5.75, 500),
        "UTILITY": (1.25, 250),
    }
    for role, (cs, dpm) in expected.items():
        bl = ROLE_BASELINES[role]
        assert bl.cs_per_min == cs
        assert bl.dpm == dpm


def test_role_desconocido_cae_al_perfil_neutro():
    """ARAM / roles sin asignar no rompen: usan DEFAULT_BASELINE."""
    assert baseline_for(None) is DEFAULT_BASELINE
    assert baseline_for("") is DEFAULT_BASELINE
    assert baseline_for("Unknown") is DEFAULT_BASELINE
    assert baseline_for("somethingweird") is DEFAULT_BASELINE


def test_expected_stats_escalan_con_la_duracion():
    """KP% es ratio 0-1; la visión total = visión/min × duración (redondeada a 1 decimal)."""
    stats = expected_stats_for("BOTTOM", 30)
    assert stats["cs_per_min"] == 7.5
    assert stats["dpm"] == 600
    assert stats["kill_participation"] == 0.65
    assert stats["vision_score"] == 9.0  # 0.3 * 30

    stats_short = expected_stats_for("UTILITY", 20)
    assert stats_short["vision_score"] == 20.0  # 1.0 * 20


def test_enrich_match_row_adjunta_expected_por_participante():
    """`enrich_match_row` enriquece en lectura y deja intactas las filas legacy."""
    row = {
        "game_duration_minutes": 25,
        "participants": [
            {"puuid": "a", "team_position": "UTILITY", "champion_name": "Thresh"},
            {"puuid": "b", "team_position": "BOTTOM", "champion_name": "Jinx"},
        ],
    }
    enriched = enrich_match_row(row)
    assert enriched is not row
    assert enriched["participants"][0]["expected_stats"]["vision_score"] == 25.0
    assert enriched["participants"][0]["expected_stats"]["dpm"] == 250
    assert enriched["participants"][1]["expected_stats"]["dpm"] == 600

    legacy = enrich_match_row({"participants": None})
    assert legacy == {"participants": None}

    rol_unknown_row = enrich_match_row(
        {"game_duration_minutes": 10, "participants": [{"team_position": None}]}
    )
    assert rol_unknown_row["participants"][0]["expected_stats"] == expected_stats_for(None, 10)