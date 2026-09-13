"""Guard anti-solapamiento del POST /api/sync (race del 409, auditoría v1.6).

Dos POST simultáneos deben producir exactamente un 202 y un 409. El bug auditado: el estado
se marcaba "processing" DESPUÉS del `await start_run`, ABRIENDO una ventana en la que dos
requests atravesaban el guard y lanzaban dos `_run_sync` (doble quema de cuota de Riot).

El `_slow_start_run` cede el bucle con `asyncio.sleep(0)` justo después del guard — replica
el write real a DB — para que el test SÍ faile si alguien reintroduce el orden viejo.

v2.1 (P0): el Riot ID ya no llega por query ni del .env — se lee de `user_settings`
(migración 014), así que se parchea `settings_repo.get` con una fila vinculada (sin DB en
herméticos). Y el estado ahora es POR USUARIO (`_states`), de modo que la limpieza pasa por
vaciar el dict del router (los tokens de `auth_headers` siempre decodifican al mismo `sub`).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.app.main import app
from backend.app.repositories import settings as settings_repo
from backend.app.repositories import sync_runs
from backend.app.routers import sync as sync_router
from backend.tests.conftest import TEST_USER_UUID, make_auth_headers


async def _slow_start_run(_user_id: object, _started_at: object) -> int:
    """Replicación del write real a DB: cede el bucle justo donde vivía el race."""
    await asyncio.sleep(0)
    return 1


async def _finish_run_noop(*args: object, **kwargs: object) -> None:
    return None


async def _run_sync_noop(*args: object, **kwargs: object) -> None:
    return None


def _patch_riot_linked(
    monkeypatch: pytest.MonkeyPatch, riot_id: str = "Lucho#EUW", region: str = "EUW1"
) -> None:
    """Fila de user_settings vinculada (sin DB): sustituye a la migración 014 en herméticos."""

    async def _fake_get(_user_id: str) -> dict:
        return {"riot_id": riot_id, "riot_region": region}

    monkeypatch.setattr(settings_repo, "get", _fake_get)


def _user_state() -> sync_router._SyncState:
    """Estado del usuario de pruebas (el mismo `sub` que decodifica auth_headers)."""
    return sync_router._states[str(TEST_USER_UUID)]


def test_dos_posts_simultaneos_solo_uno_pasa(monkeypatch, auth_headers):
    """`asyncio.gather` de dos POST /api/sync: exactamente un 202 y un 409.

    El resto de la cadena (Riot, finishes, `_run_sync`) se parchea a no-op: el test sólo
    verifica el guard, que es la superficie del race. Sin pool ni red.
    """
    monkeypatch.setattr(sync_runs, "start_run", _slow_start_run)
    monkeypatch.setattr(sync_runs, "finish_run", _finish_run_noop)
    monkeypatch.setattr(sync_router, "_run_sync", _run_sync_noop)
    _patch_riot_linked(monkeypatch)

    async def _scenario() -> None:
        sync_router._states.clear()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1, r2 = await asyncio.gather(
                client.post("/api/sync", headers=auth_headers),
                client.post("/api/sync", headers=auth_headers),
            )

            codes = sorted([r1.status_code, r2.status_code])
            assert codes == [202, 409], f"esperaba un 202 y un 409, llegó {codes}"

            # Mientras el run siga en vuelo, el guard debe seguir bloqueando (mismo usuario).
            third = await client.post("/api/sync", headers=auth_headers)
            assert third.status_code == 409
            assert "en curso" in third.json()["detail"]

            # Otra identidad distinta NO debe chocar con el sync de este usuario (P0: el
            # estado está aislado por user_id, el 409 es por-usuario).
            other_headers = make_auth_headers(sub="00000000-0000-0000-0000-000000000002")
            r_other = await client.post("/api/sync", headers=other_headers)
            assert r_other.status_code == 202

    try:
        asyncio.run(_scenario())
    finally:
        sync_router._states.clear()


def test_sync_tras_fallo_en_start_run_vuelve_a_idle(monkeypatch, auth_headers):
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
    _patch_riot_linked(monkeypatch)

    async def _scenario() -> None:
        sync_router._states.clear()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with pytest.raises(RuntimeError, match="DB caída"):
                await client.post("/api/sync", headers=auth_headers)
        assert _user_state().status == "idle"

    try:
        asyncio.run(_scenario())
    finally:
        sync_router._states.clear()


def test_sync_sin_riot_vinculado_da_400_y_no_deja_processing(monkeypatch, auth_headers):
    """Sin `riot_id` en user_settings, el POST responde 400 y restaura "idle".

    Nuevo camino de v2.1 (P0): el sync ya no cae a `RIOT_ID` del .env — si el usuario no
    vinculó su cuenta Riot, se responde con instrucciones y el estado no queda pegado.
    """
    _patch_riot_linked(monkeypatch, riot_id="", region="")  # fila sin vincular

    async def _scenario() -> None:
        sync_router._states.clear()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/api/sync", headers=auth_headers)
        assert r.status_code == 400
        assert "no está vinculada" in r.json()["detail"]
        assert _user_state().status == "idle"

    try:
        asyncio.run(_scenario())
    finally:
        sync_router._states.clear()