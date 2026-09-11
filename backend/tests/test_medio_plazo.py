"""Tests herméticos de la lógica pura del bloque Medio Plazo #2.

Sin DB y sin Riot: se prueban `assess_meta_verdict_row` (regla de meta-shift), la selección
de maestrías del scout (`top_mastery_champions`) y el TTL de la caché (`cache_is_fresh`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.app.repositories.scout import SCOUT_CACHE_TTL, cache_is_fresh
from backend.app.repositories.stats import assess_meta_verdict_row
from backend.app.services.scout import top_mastery_champions


# ───────────────────────────────── veredicto del meta ─────────────────────────────────


def _row(**overrides) -> dict:
    return {
        "user_champion": "Jax",
        "enemy_champion": "Darius",
        "games_current": 3,
        "wins_current": 1,
        "games_previous": 20,
        "wins_previous": 14,
        **overrides,
    }


def test_meta_verdict_favorable_que_sigue_favorable():
    result = assess_meta_verdict_row(_row(games_current=3, wins_current=2))
    assert result["winrate_current"] == 66.7
    assert result["winrate_previous"] == 70.0
    assert result["delta_pp"] == -3.3
    assert result["meta_shift"] is False


def test_meta_shift_cuando_favorable_se_vuelve_negativo():
    # 70% histórico (favorable) -> 33% en el parche actual con muestra: META SHIFT.
    result = assess_meta_verdict_row(_row(games_current=3, wins_current=1))
    assert result["winrate_current"] == 33.3
    assert result["meta_shift"] is True


def test_meta_shift_no_salta_con_muestra_insuficiente():
    # El mismo cruce con sólo 1 partida en el parche actual: demasiado poco para cantar el shift.
    result = assess_meta_verdict_row(_row(games_current=1, wins_current=0))
    assert result["meta_shift"] is False


def test_meta_shift_requiere_favorable_previo():
    # Histórico mediocre (45%) que además cae: no es un shift, es que nunca fue favorable.
    result = assess_meta_verdict_row(_row(games_current=5, wins_current=1, games_previous=10, wins_previous=5))
    assert result["winrate_previous"] == 50.0
    assert result["meta_shift"] is False


def test_sin_partidas_actuales_winrate_none():
    result = assess_meta_verdict_row(_row(games_current=0, wins_current=0))
    assert result["winrate_current"] is None
    assert result["delta_pp"] is None
    assert result["meta_shift"] is False


# ─────────────────────────────── escout (maestrías) ───────────────────────────────


_NAME_BY_KEY = {"103": "Ahri", "63": "Jax", "20": "Nunu & Willump", "999": "OneForAll"}


def test_top_mastery_ordena_por_puntos_y_traduce_la_key():
    entries = [
        {"championId": 20, "championLevel": 7, "championPoints": 310_000},
        {"championId": 103, "championLevel": 5, "championPoints": 120_000},
        {"championId": 63, "championLevel": 4, "championPoints": 250_000},
    ]
    top = top_mastery_champions(entries, _NAME_BY_KEY, limit=3)
    assert [c["champion"] for c in top] == ["Nunu & Willump", "Jax", "Ahri"]
    assert top[0]["mastery_level"] == 7
    assert top[0]["points"] == 310_000
    assert top[1]["champion_key"] == "63"


def test_top_mastery_recorta_a_tres():
    entries = [
        {"championId": i, "championLevel": 5, "championPoints": 100_000 + i}
        for i in range(1, 6)
    ]
    top = top_mastery_champions(entries, _NAME_BY_KEY)
    assert len(top) == 3
    assert [c["points"] for c in top] == [100_005, 100_004, 100_003]


def test_top_mastery_key_desconocida_no_inventa_nombre():
    entries = [{"championId": 42, "championLevel": 7, "championPoints": 500_000}]
    assert top_mastery_champions(entries, _NAME_BY_KEY) == [
        {"champion": "#42", "champion_key": "42", "mastery_level": 7, "points": 500_000}
    ]


# ─────────────────────────────── caché del escout ───────────────────────────────


def test_cache_fresh_dentro_del_ttl():
    now = datetime.now(UTC)
    cached_at = now - timedelta(hours=1)
    assert cache_is_fresh(cached_at, now) is True


def test_cache_expirada_fuera_del_ttl():
    now = datetime.now(UTC)
    cached_at = now - (SCOUT_CACHE_TTL + timedelta(minutes=1))
    assert cache_is_fresh(cached_at, now) is False


def test_cache_justo_en_el_borde_del_ttl():
    now = datetime.now(UTC)
    cached_at = now - SCOUT_CACHE_TTL
    # En el límite exacto se considera válida (<= no <).
    assert cache_is_fresh(cached_at, now) is True