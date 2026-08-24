"""Health check. Diagnostica de golpe los bloqueadores típicos del proyecto:
credenciales de Supabase caducadas, pool caído, etc.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.app import db
from backend.app.deps import SettingsDep
from backend.app.schemas import HealthStatus

log = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health(settings: SettingsDep) -> HealthStatus:
    warnings: list[str] = []

    db_ok = True
    try:
        await db.fetch_one("SELECT 1 AS ok")
    except Exception as exc:  # noqa: BLE001 - health nunca debe reventar, sólo reportar
        db_ok = False
        log.error("Health check de DB falló: %s", exc)
        warnings.append(
            "Sin conexión a Supabase. Si es 'password authentication failed', rota "
            "DB_PASSWORD en Supabase (Settings › Database) y actualiza .env."
        )

    return HealthStatus(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        riot_key_present=bool(settings.riot_api_key),
        warnings=warnings,
    )
