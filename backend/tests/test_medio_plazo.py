"""Tests herméticos de la lógica pura del bloque Medio Plazo #2.

Sin DB y sin Riot: se prueban `assess_meta_verdict_row` (regla de meta-shift), la selección
de maestrías del scout (`top_mastery_champions`), el TTL de la caché (`cache_is_fresh`) y el
contrato de la caché negativa del escout (429/5xx -> estado fallido, sin llamada a Riot).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.repositories.scout import (
    SCOUT_CACHE_TTL,
    SCOUT_ERROR_TTL,
    cache_is_fresh,
)
from backend.app.repositories.stats import assess_meta_verdict_row
from backend.app.services import scout as scout_service
from backend.app.services.riot import RiotServiceError
from backend.app.services.scout import (
    ScoutUnavailableError,
    top_mastery_champions,
)


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


# ─────────────────────────── caché negativa (429/5xx) ───────────────────────────


def test_error_ttl_es_mucho_mas_corto_que_el_de_exito():
    # La caché negativa debe expirar antes que la positiva: 15 min de tregua vs 24 h de dato.
    assert SCOUT_ERROR_TTL < SCOUT_CACHE_TTL


def test_error_negativo_fresco_y_expirado_dentro_de_15_minutos():
    now = datetime.now(UTC)
    assert cache_is_fresh(now - timedelta(minutes=14), now, ttl=SCOUT_ERROR_TTL) is True
    assert cache_is_fresh(now - timedelta(minutes=16), now, ttl=SCOUT_ERROR_TTL) is False


def _match_row(champion="Jax", enemy="Darius") -> dict:
    return {
        "game_id": "EUW1_1",
        "champion": champion,
        "enemy_champion": enemy,
        "participants": [
            {"champion_name": champion, "puuid": "p-me", "player_name": "Yo#EUW",
             "team_id": 100, "team_position": "TOP"},
            {"champion_name": enemy, "puuid": "p-rival", "player_name": "Rival#EUW",
             "team_id": 200, "team_position": "TOP"},
        ],
    }


def test_retryable_error_guarda_estado_fallido_y_sirve_503():
    """Un 429/5xx (retryable) escribe la caché negativa y sube ScoutUnavailableError con aviso."""
    async def _run() -> None:
        mock_error = AsyncMock()
        mock_write_ok = AsyncMock()
        with (
            patch("backend.app.services.scout.get_settings"),
            patch(
                "backend.app.services.scout.datadragon.get_champions",
                new_callable=AsyncMock,
                return_value={"champions": {}},
            ),
            patch(
                "backend.app.repositories.scout.get_scout_cache",
                new_callable=AsyncMock,
                return_value=(None, None, ""),
            ),
            patch("backend.app.repositories.scout.set_scout_cache", mock_write_ok),
            patch("backend.app.repositories.scout.set_scout_cache_error", mock_error),
            patch("backend.app.services.scout.RiotService") as MockRS,
        ):
            instance = MockRS.return_value
            instance.fetch_champion_mastery = AsyncMock(
                side_effect=RiotServiceError("Rate limit", status=429, retryable=True)
            )
            with pytest.raises(ScoutUnavailableError) as exc_info:
                await scout_service.scout_opponent_for_match(_match_row())
            assert "cacheado" in str(exc_info.value).lower()
            # La caché positiva NO se tocó; la negativa sí, con ese puuid.
            mock_write_ok.assert_not_awaited()
            mock_error.assert_awaited_once_with("p-rival", "Rate limit")

    asyncio.run(_run())


def test_error_no_retryable_no_se_cachea():
    """Un 403 (key expirada) se informa sin caché: cachear lo ocultaría en reaperturas."""
    async def _run() -> None:
        mock_error = AsyncMock()
        mock_write_ok = AsyncMock()
        with (
            patch("backend.app.services.scout.get_settings"),
            patch(
                "backend.app.services.scout.datadragon.get_champions",
                new_callable=AsyncMock,
                return_value={"champions": {}},
            ),
            patch(
                "backend.app.repositories.scout.get_scout_cache",
                new_callable=AsyncMock,
                return_value=(None, None, ""),
            ),
            patch("backend.app.repositories.scout.set_scout_cache", mock_write_ok),
            patch("backend.app.repositories.scout.set_scout_cache_error", mock_error),
            patch("backend.app.services.scout.RiotService") as MockRS,
        ):
            instance = MockRS.return_value
            instance.fetch_champion_mastery = AsyncMock(
                side_effect=RiotServiceError("API Key expirada", status=403, retryable=False)
            )
            with pytest.raises(ScoutUnavailableError):
                await scout_service.scout_opponent_for_match(_match_row())
            mock_error.assert_not_awaited()
            mock_write_ok.assert_not_awaited()

    asyncio.run(_run())


def test_estado_fallido_fresco_evita_llamar_a_riot():
    """Caché negativa fresca -> 503 directo SIN tocar la API de Riot."""
    async def _run() -> None:
        mock_fetch = AsyncMock(return_value=[])
        with (
            patch(
                "backend.app.repositories.scout.get_scout_cache",
                new_callable=AsyncMock,
                return_value=(
                    None,
                    datetime.now(UTC),
                    "Rate limit de Riot excedido.",
                ),
            ),
            patch("backend.app.services.scout.RiotService") as MockRS,
        ):
            MockRS.return_value.fetch_champion_mastery = mock_fetch
            with pytest.raises(ScoutUnavailableError) as exc_info:
                await scout_service.scout_opponent_for_match(_match_row())
            assert "cacheado" in str(exc_info.value).lower() or "limitando" in str(exc_info.value).lower()
            # El contrato clave: Riot NO se ha llamado.
            mock_fetch.assert_not_called()

    asyncio.run(_run())


def test_dos_requests_concurrentes_solo_una_llamada_riot():
    """El lock por puuid serializa: dos coroutines del mismo rival -> una sola llamada a Riot.

    Se simula la tabla `scout_cache` con un dict en memoria (get/set espejo del repo) para
    que el double-check tras el lock vea la caché recién llenada por el primer request.
    """
    async def _run() -> None:
        fetch_count = 0
        db_fake: dict[str, tuple[list, datetime, str]] = {}

        def fake_get(puuid: str):
            return db_fake.get(puuid, (None, None, ""))

        async def fake_set(puuid: str, payload: list) -> None:
            db_fake[puuid] = (payload, datetime.now(UTC), "")

        async def fake_error(puuid: str, error: str) -> None:
            db_fake[puuid] = ([], datetime.now(UTC), error)

        async def fake_riot_fetch(puuid: str):
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.05)
            return [{"championId": 63, "championLevel": 7, "championPoints": 400_000}]

        with (
            patch("backend.app.services.scout.get_settings"),
            patch(
                "backend.app.services.scout.datadragon.get_champions",
                new_callable=AsyncMock,
                return_value={"champions": {"63": {"key": "63", "name": "Jax"}}},
            ),
            patch("backend.app.repositories.scout.get_scout_cache", side_effect=fake_get),
            patch("backend.app.repositories.scout.set_scout_cache", new_callable=AsyncMock, side_effect=fake_set),
            patch("backend.app.repositories.scout.set_scout_cache_error", new_callable=AsyncMock, side_effect=fake_error),
            patch("backend.app.services.scout.RiotService") as MockRS,
        ):
            MockRS.return_value.fetch_champion_mastery = fake_riot_fetch

            await asyncio.gather(
                scout_service.scout_opponent_for_match(_match_row()),
                scout_service.scout_opponent_for_match(_match_row()),
            )
            # El segundo request encontró la caché caliente tras esperar el lock.
            assert fetch_count == 1, "El lock + double-check deben evitar re-llamar a Riot"

    asyncio.run(_run())