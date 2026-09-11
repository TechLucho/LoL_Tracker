"""Guard anti-solapamiento del POST /api/sync (race del 409, auditoría v1.6).

Dos POST simultáneos deben producir exactamente un 202 y un 409. El bug auditado: el estado
se marcaba "processing" DESPUÉS del `await start_run`, ABRIENDO una ventana en la que dos
requests atravesaban el guard y lanzaban dos `_run_sync` (doble quema de cuota de Riot).

El `_slow_start_run` cede el bucle con `asyncio.sleep(0)` justo después del guard — replica
el write real a DB — para que el test SÍ faile si alguien reintroduce el orden viejo.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.app.main import app
from backend.app.repositories import sync_runs
from backend.app.routers import sync as sync_router


async def _slow_start_run(_started_at: object) -> int:
    """Replicación del write real a DB: cede el bucle justo donde vivía el race."""
    await asyncio.sleep(0)
    return 1


async def _finish_run_noop(*args: object, **kwargs: object) -> None:
    return None


async def _run_sync_noop(*args: object, **kwargs: object) -> None:
    return None


def test_dos_posts_simultaneos_solo_uno_pasa(monkeypatch):
    """`asyncio.gather` de dos POST /api/sync: exactamente un 202 y un 409.

    El resto de la cadena (Riot, finishes, `_run_sync`) se parchea a no-op: el test sólo
    verifica el guard, que es la superficie del race. Sin pool ni red.
    """
    monkeypatch.setattr(sync_runs, "start_run", _slow_start_run)
    monkeypatch.setattr(sync_runs, "finish_run", _finish_run_noop)
    monkeypatch.setattr(sync_router, "_run_sync", _run_sync_noop)

    async def _scenario() -> None:
        sync_router._state.status = "idle"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1, r2 = await asyncio.gather(
                client.post("/api/sync", params={"riot_id": "Lucho#EUW"}),
                client.post("/api/sync", params={"riot_id": "Lucho#EUW"}),
            )

            codes = sorted([r1.status_code, r2.status_code])
            assert codes == [202, 409], f"esperaba un 202 y un 409, llegó {codes}"

            # Mientras el run siga en vuelo, el guard debe seguir bloqueando.
            third = await client.post("/api/sync", params={"riot_id": "Lucho#EUW"})
            assert third.status_code == 409
            assert "en curso" in third.json()["detail"]

    try:
        asyncio.run(_scenario())
    finally:
        sync_router._state.status = "idle"
        sync_router._state.result = None
        sync_router._state.error = None


def test_sync_tras_fallo_en_start_run_vuelve_a_idle(monkeypatch):
    """Si `start_run` revienta (DB caída), el estado vuelve a "idle": no hay 409 pegado.

    Regresión del comentario original de 006: un fallo de persistencia NO debe dejar el
    endpoint escupiendo 409 para siempre. Con ASGITransport el ServerErrorMiddleware
    re-lanza la excepción en vez de responder 500: lo que importa es el estado.
    """
    async def _boom(*args: object, **kwargs: object) -> int:
        raise RuntimeError("DB caída")

    async def _run_sync_noop2(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(sync_runs, "start_run", _boom)
    monkeypatch.setattr(sync_runs, "finish_run", _finish_run_noop)
    monkeypatch.setattr(sync_router, "_run_sync", _run_sync_noop2)

    async def _scenario() -> None:
        sync_router._state.status = "idle"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with pytest.raises(RuntimeError, match="DB caída"):
                await client.post("/api/sync", params={"riot_id": "Lucho#EUW"})
        assert sync_router._state.status == "idle"

    try:
        asyncio.run(_scenario())
    finally:
        sync_router._state.status = "idle"
        sync_router._state.result = None
        sync_router._state.error = None