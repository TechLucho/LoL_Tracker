"""Sync Reanudable end-to-end contra Postgres real (migraciones 006 + 012 aplicadas).

Cubre el compromiso central del hito: cuando Riot degrada, `_run_sync` NO marca el sync como
error (500) — cierra en 'partial', escribe `sync_runs.status = 'partial'` (exigido por el CHECK
de la migración 012) y deja `SyncResult.degraded_api = True` para que la UI avise de que hay
que reintentar. Requiere TEST_DATABASE_URL (solo CI; local se ignora vía conftest).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from backend.app import db
from backend.app.repositories import sync_runs
from backend.app.services.riot import RiotDegradedError

pytestmark = pytest.mark.integration


class _DegradedRiot:
    """RiotService falso que degrada antes de devolver la primera partida."""

    async def fetch_recent_matches(self, riot_id: str, limit: int = 10, queue: int | None = 420,
                                   *, on_match=None) -> tuple[list, list]:
        raise RiotDegradedError("Riot degradado: 500 sostenido", status=500)


def test_sync_degradado_cierra_en_partial():
    from backend.app.routers import sync as sync_router

    async def _scenario() -> None:
        sync_router._state.status = "idle"
        sync_router._state.result = None
        sync_router._state.error = None

        started = datetime.now(UTC)
        run_id = await sync_runs.start_run(started)
        await sync_router._run_sync(_DegradedRiot(), "Test#EUW", 10, [420, 400], run_id=run_id)

        # Estado en memoria para el polling: 'partial', no 'error' ni 'success'.
        assert sync_router._state.status == "partial"
        assert sync_router._state.error is None
        assert sync_router._state.result is not None
        assert sync_router._state.result.degraded_api is True

        # Auditoría: el run cerró como 'partial' (CHECK de la migración 012 lo permite).
        runs = await sync_runs.recent_runs(limit=1)
        assert runs and runs[0]["status"] == "partial"

    async def _main() -> None:
        await db.open_pool()
        try:
            await db.execute("TRUNCATE sync_runs RESTART IDENTITY")
            await _scenario()
        finally:
            await db.close_pool()

    asyncio.run(_main())