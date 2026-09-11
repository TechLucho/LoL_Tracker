"""La Constitución — exposición HTTP del motor anti-tilt.

Sólo une la configuración persistida con la ventana de partidas y delega el veredicto en
`services.constitution.evaluate_rules` (lógica pura, testeada de forma hermética).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.app.repositories import matches as matches_repo
from backend.app.repositories import settings as settings_repo
from backend.app.services.constitution import RECENT_WINDOW, evaluate_rules

router = APIRouter(prefix="/api/constitution", tags=["constitution"])


@router.get("/status")
async def constitution_status() -> dict[str, Any]:
    cfg = await settings_repo.get()
    # Últimas N partidas válidas (máximo; puede haber menos): sólo Solo/Duo de 5+ minutos,
    # para que un remake no dispare el STOP ni contamine la media de muertes. Ver
    # matches_repo.last_results().
    recent = await matches_repo.last_results(limit=RECENT_WINDOW)
    return evaluate_rules(
        champion_pool=cfg.get("champion_pool") or [],
        max_deaths=float(cfg.get("max_deaths") or 8),
        target_cs_min=float(cfg.get("target_cs_min") or 7.0),
        recent=recent,
    )