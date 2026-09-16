"""Configuración del usuario.

- GET /api/config  → config completa (canónica + persistida del usuario)
- PUT /api/config  → actualiza champion pool y OKRs
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.config import ROUTING_MAP, get_settings
from backend.app.deps import CurrentUserId
from backend.app.repositories import settings as repo
from backend.app.schemas import (
    CHAMPION_POOL_MAX,
    IMPACT_RATINGS,
    UserSettings,
    UserSettingsUpdate,
)

router = APIRouter(tags=["config"])


@router.get("/api/config", response_model=UserSettings)
async def get_config(user_id: CurrentUserId) -> UserSettings:
    """Config completa: canónicos del sistema + configuración persistida del usuario.

    En Streamlit, `IMPACT_RATINGS` estaba hardcodeado en dos formularios distintos con riesgo
    de divergencia. Ahora vive en un solo sitio y se sirve desde la API.
    """
    settings = get_settings()
    row = await repo.get(user_id)
    # `row` (migración 014) ya trae riot_id/riot_region: pasar argumentos explícitos JUNTO a
    # `**row` duplica keyword args y explota con TypeError. Se construye el dict limpio y se
    # desempaqueta una sola vez.
    row_dict = dict(row)
    row_dict["riot_region"] = (row_dict.get("riot_region") or "EUW1").upper()
    row_dict["riot_id"] = (row_dict.get("riot_id") or "").strip()
    return UserSettings(
        **row_dict,
        impact_ratings=list(IMPACT_RATINGS),
        regions=sorted(ROUTING_MAP.keys()),
        champion_pool_max=CHAMPION_POOL_MAX,
        display_timezone=settings.display_timezone,
    )


@router.put("/api/config", response_model=UserSettings)
async def update_config(user_id: CurrentUserId, payload: UserSettingsUpdate) -> UserSettings:
    """Reemplaza champion pool y OKRs (PUT semantics).

    El pool se limpia en el servidor: quita blancos y duplicados, respeta el máximo de 3
    (regla de La Constitución).
    """
    row = await repo.replace(
        user_id,
        champion_pool=payload.champion_pool,
        target_cs_min=payload.target_cs_min,
        max_deaths=payload.max_deaths,
        target_dpm=payload.target_dpm,
        target_kp_percent=payload.target_kp_percent,
        target_vision_score=payload.target_vision_score,
    )
    # RETURNING * incluye riot_id/riot_region (migración 014): normalizar igual que en GET
    # para que NULL ('euw1' en minúsculas) no rompa UserSettings.
    row_dict = dict(row)
    row_dict["riot_region"] = (row_dict.get("riot_region") or "EUW1").upper()
    row_dict["riot_id"] = (row_dict.get("riot_id") or "").strip()
    return UserSettings(**row_dict)
