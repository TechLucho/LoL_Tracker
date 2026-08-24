"""Métricas agregadas: resumen, champion pool, heatmap y tendencia de LP."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.deps import SettingsDep
from backend.app.repositories import matches as matches_repo
from backend.app.repositories import stats as repo
from backend.app.schemas import ChampionStats, ConstitutionStatus, HeatmapCell, StatsSummary
from backend.app.services import constitution

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
async def summary() -> StatsSummary:
    """Promedios como números. El monolito devolvía la KDA como el string "5.0 / 2.0 / 10.0",
    que la UI re-parseaba con `.split('/')` — origen del bug de `app.py:128`."""
    return StatsSummary(**await repo.summary())


@router.get("/champions", response_model=list[ChampionStats])
async def champions() -> list[ChampionStats]:
    """Incluye `winrate` y `kda_ratio` calculados en SQL: las dos columnas que la Tab 3 de
    Streamlit pedía y que la query nunca devolvía."""
    return [ChampionStats(**row) for row in await repo.champion_performance()]


@router.get("/heatmap", response_model=list[HeatmapCell])
async def heatmap(settings: SettingsDep) -> list[HeatmapCell]:
    rows = await repo.activity_heatmap(settings.display_timezone)
    return [HeatmapCell(**row) for row in rows]


@router.get("/lp-trend")
async def lp_trend(limit: int = 20, queue: int | None = None) -> list[dict]:
    """LP acumulado en orden cronológico. `has_lp` distingue "0 LP" de "aún sin registrar".

    `queue` acota la cola (420 = Solo/Duo): las normales sin LP diluyen la curva si cuentan como 0.
    """
    return await repo.lp_trend(limit=limit, queue_id=queue)


@router.get("/constitution", response_model=ConstitutionStatus)
async def constitution_status() -> ConstitutionStatus:
    recent = await matches_repo.last_results(limit=constitution.BLOCK_SIZE)
    return ConstitutionStatus(**constitution.evaluate(recent))
