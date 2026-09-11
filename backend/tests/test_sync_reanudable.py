"""Tests herméticos del Sync Reanudable (Largo Plazo v2.0, hito 1).

Sin DB y sin Riot: se prueban (a) el cortacircuitos `RiotDegradedError` de `_call_with_retry`
— un 429 con Retry-After > 60s aborta al instante sin dormir el backoff, y un 5xx agotado NO
sube como error genérico sino como degradación — y (b) el streaming de `fetch_recent_matches`
(el callback `on_match` corre por cada partida procesada y un degradado a mitad de descarga
propaga para que el sync cierre en 'partial' con lo ya guardado).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from riotwatcher import ApiError

from backend.app.services import riot as riot_module
from backend.app.services.riot import RiotDegradedError, RiotService, RiotServiceError


class _FakeResponse:
    """Response mínima de requests: `_classify` y `_retry_after` sólo leen estos dos campos."""

    def __init__(self, status: int, headers: dict):
        self.status_code = status
        self.headers = headers


def _http_error(status: int, retry_after: str | None = None) -> ApiError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return ApiError(f"HTTP {status}", response=_FakeResponse(status, headers))


def _fresh_service() -> RiotService:
    """Instancia sin `__init__` (evita Settings/red): `_call_with_retry` REAL (probando el
    cortacircuito) y watchers stub para que los argumentos a Riot se evalúen sin red."""

    class _Leaf:
        # Callables: `fetch_recent_matches` los envuelve con functools.partial en el momento
        # de la llamada (aunque `_call_with_retry` esté parcheado, los argumentos se evalúan).
        by_riot_id = lambda *a, **k: None
        by_puuid = lambda *a, **k: None
        matchlist_by_puuid = lambda *a, **k: None
        by_id = lambda *a, **k: None
        by_summoner = lambda *a, **k: None
        timeline_by_match = lambda *a, **k: None

    class _Watcher:
        account = _Leaf()
        match = _Leaf()
        summoner = _Leaf()
        league = _Leaf()
        champion_mastery = _Leaf()

    svc = RiotService.__new__(RiotService)
    svc._route = "eu1"
    svc._platform = "EUW1"
    svc._lol = _Watcher()
    svc._riot = _Watcher()
    return svc


def _clear_puuid_cache() -> None:
    riot_module._puuid_cache.clear()


# ─────────────────────────── cortacircuitos de degradación ───────────────────────────


def test_429_con_retry_after_largo_aborta_degradado_sin_backoff():
    """Retry-After > 60s = 'Riot caído a largo plazo': no se espera, se aborta al momento."""
    async def _run() -> None:
        svc = _fresh_service()
        with (
            patch(
                "backend.app.services.riot.run_in_threadpool",
                side_effect=_http_error(429, "90"),
            ),
            patch(
                "backend.app.services.riot.asyncio.sleep", new_callable=AsyncMock
            ) as sleep_mock,
        ):
            with pytest.raises(RiotDegradedError) as exc_info:
                await svc._call_with_retry("prueba", lambda: "nunca")
            assert exc_info.value.status == 429
            assert exc_info.value.retryable is False
            sleep_mock.assert_not_awaited()  # el contracircuito evita dormir el proceso

    asyncio.run(_run())


def test_5xx_sostenido_agotado_lanza_degradado():
    """Todos los intentos con 500: se distingue 'Riot caído' y NO se reporta como error genérico."""
    async def _run() -> None:
        svc = _fresh_service()
        with (
            patch(
                "backend.app.services.riot.run_in_threadpool",
                side_effect=_http_error(500),
            ),
            patch(
                "backend.app.services.riot.asyncio.sleep", new_callable=AsyncMock
            ) as sleep_mock,
        ):
            with pytest.raises(RiotDegradedError) as exc_info:
                await svc._call_with_retry("prueba", lambda: "nunca")
            assert exc_info.value.status == 500
            assert exc_info.value.retryable is False
            # Se reintentó con backoff antes de declarar la degradación (3 intentos -> 2 esperas).
            assert sleep_mock.await_count == 2

    asyncio.run(_run())


def test_429_corto_sigue_reintentando_y_no_degrada():
    """Retry-After corto es un rate limit normal: backoff y a la tercera se informa sin degradar."""
    async def _run() -> None:
        svc = _fresh_service()
        with (
            patch(
                "backend.app.services.riot.run_in_threadpool",
                side_effect=_http_error(429, "10"),
            ),
            patch(
                "backend.app.services.riot.asyncio.sleep", new_callable=AsyncMock
            ) as sleep_mock,
        ):
            with pytest.raises(RiotServiceError) as exc_info:
                await svc._call_with_retry("prueba", lambda: "nunca")
            assert exc_info.value.status == 429
            assert not isinstance(exc_info.value, RiotDegradedError)
            assert sleep_mock.await_count == 2

    asyncio.run(_run())


def test_403_no_reintenta_y_no_degrada():
    """Un 403 (key expirada) falla a la primera y jamás se etiqueta como degradado."""
    async def _run() -> None:
        svc = _fresh_service()
        with (
            patch(
                "backend.app.services.riot.run_in_threadpool",
                side_effect=_http_error(403),
            ),
            patch(
                "backend.app.services.riot.asyncio.sleep", new_callable=AsyncMock
            ) as sleep_mock,
        ):
            with pytest.raises(RiotServiceError) as exc_info:
                await svc._call_with_retry("prueba", lambda: "nunca")
            assert exc_info.value.status == 403
            assert not isinstance(exc_info.value, RiotDegradedError)
            sleep_mock.assert_not_awaited()

    asyncio.run(_run())


# ────────────────────── streaming de fetch_recent_matches ──────────────────────


def _participant(
    puuid: str, name: str, champ: str, team_id: int, win: bool
) -> dict:
    return {
        "puuid": puuid,
        "riotIdGameName": name,
        "riotIdTagline": "EUW",
        "championName": champ,
        "teamPosition": "TOP",
        "individualPosition": "TOP",
        "teamId": team_id,
        "win": win,
        "kills": 3, "deaths": 2, "assists": 4,
        "totalMinionsKilled": 150, "neutralMinionsKilled": 20,
        "visionWardsBoughtInGame": 3,
        "totalDamageDealtToChampions": 12_000,
        "totalDamageTaken": 15_000,
        "goldEarned": 10_000,
        "visionScore": 12,
        "item0": 3153, "item1": 3071, "item2": 3047, "item3": 3078,
        "item4": 0, "item5": 0, "item6": 3340,
        "summoner1Id": 4, "summoner2Id": 6,
    }


def _raw_match(game_id: str) -> dict:
    return {
        "metadata": {"matchId": game_id, "gameVersion": "14.18.586.6903"},
        "info": {
            "gameEndTimestamp": 1_754_000_000_000,
            # < 15 min: `_attach_laning` se salta el timeline y no consume más llamadas.
            "gameDuration": 600,
            "gameQueueConfigId": 420,
            "queueId": 420,
            "participants": [
                _participant("p-me", "Stream", "Jax", 100, True),
                _participant("p-rival", "Rival", "Darius", 200, False),
            ],
        },
    }


def test_fetch_recent_matches_ejecuta_on_match_por_cada_partida():
    async def _run() -> None:
        _clear_puuid_cache()
        svc = _fresh_service()
        svc._call_with_retry = AsyncMock(side_effect=[
            {"puuid": "p-me", "gameName": "Stream", "tagLine": "EUW"},
            ["EUW1_g1", "EUW1_g2"],
            _raw_match("EUW1_g1"),
            _raw_match("EUW1_g2"),
        ])
        checkpointed: list[str] = []

        async def _on_match(match: dict) -> None:
            checkpointed.append(match["game_id"])

        matches, failures = await svc.fetch_recent_matches(
            "Streaming#EUW", limit=2, queue=420, on_match=_on_match,
        )
        # El checkpoint corre por cada partida, en orden, antes de devolver la lista final.
        assert [m["game_id"] for m in matches] == ["EUW1_g1", "EUW1_g2"]
        assert checkpointed == ["EUW1_g1", "EUW1_g2"]
        assert failures == []

    asyncio.run(_run())


def test_fetch_recent_matches_propaga_degradado_con_lo_checkpointado():
    """Un degradado a mitad de descarga: lo ya procesado se notificó (commit parcial posible)
    y el error NO se traga en failures — propaga para que el sync cierre en 'partial'."""
    async def _run() -> None:
        _clear_puuid_cache()
        svc = _fresh_service()
        svc._call_with_retry = AsyncMock(side_effect=[
            {"puuid": "p-me", "gameName": "Stream", "tagLine": "EUW"},
            ["EUW1_g1", "EUW1_g2"],
            _raw_match("EUW1_g1"),
            RiotDegradedError("Riot degradado: 500 sostenido", status=500),
        ])
        checkpointed: list[str] = []

        async def _on_match(match: dict) -> None:
            checkpointed.append(match["game_id"])

        with pytest.raises(RiotDegradedError):
            await svc.fetch_recent_matches(
                "Streaming#EUW", limit=2, queue=420, on_match=_on_match,
            )
        # La partida ya descargada SÍ se notificó antes del aborto: la puede commitear el router.
        assert checkpointed == ["EUW1_g1"]

    asyncio.run(_run())