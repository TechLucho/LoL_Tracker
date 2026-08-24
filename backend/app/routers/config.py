"""Configuración del usuario y metadatos del frontend.

- GET /api/config  → config completa (canónica + persistida del usuario)
- PUT /api/config  → actualiza champion pool y OKRs
- GET /api/datadragon/version → parche actual de Data Dragon
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.config import ROUTING_MAP, get_settings
from backend.app.repositories import settings as repo
from backend.app.schemas import (
    CHAMPION_POOL_MAX,
    IMPACT_RATINGS,
    UserSettings,
    UserSettingsUpdate,
)
from backend.app.services import datadragon

router = APIRouter(tags=["config"])


@router.get("/api/config", response_model=UserSettings)
async def get_config() -> UserSettings:
    """Config completa: canónicos del sistema + configuración persistida del usuario.

    En Streamlit, `IMPACT_RATINGS` estaba hardcodeado en dos formularios distintos con riesgo
    de divergencia. Ahora vive en un solo sitio y se sirve desde la API.
    """
    settings = get_settings()
    row = await repo.get()
    return UserSettings(
        **row,
        impact_ratings=list(IMPACT_RATINGS),
        regions=sorted(ROUTING_MAP.keys()),
        champion_pool_max=CHAMPION_POOL_MAX,
        display_timezone=settings.display_timezone,
        riot_id=settings.riot_id,
        riot_region=settings.riot_region,
    )


@router.put("/api/config", response_model=UserSettings)
async def update_config(payload: UserSettingsUpdate) -> UserSettings:
    """Reemplaza champion pool y OKRs (PUT semantics).

    El pool se limpia en el servidor: quita blancos y duplicados, respeta el máximo de 3
    (regla de La Constitución).
    """
    row = await repo.replace(
        champion_pool=payload.champion_pool,
        target_cs_min=payload.target_cs_min,
        max_deaths=payload.max_deaths,
    )
    return UserSettings(**row)


@router.get("/api/datadragon/version")
async def get_datadragon_version() -> dict[str, str]:
    """Parche actual de Data Dragon. El frontend lo usa para URLs de iconos.

    Resuelve dinámicamente el hardcodeo de `current_patch = "14.24.1"` (app.py:530).
    Caché de 1h en el backend.
    """
    try:
        patch = await datadragon.get_current_patch()
    except Exception as exc:
        # Sin fallback hardcodeado a propósito: mentir con un parche viejo da 404s silenciosos.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Data Dragon no disponible y sin caché previa",
        ) from exc
    return {"patch": patch}
