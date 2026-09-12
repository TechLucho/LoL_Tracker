"""Métricas agregadas: resumen, champion pool, heatmap y tendencia de LP."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.deps import CurrentUserId, SettingsDep
from backend.app.repositories import stats as repo
from backend.app.schemas import (
    BaselineStats,
    ChampionRoleSummary,
    ChampionStats,
    HeatmapCell,
    HeatmapResponse,
    LaningSummary,
    MatchupStats,
    MetaVerdict,
    MetaVerdictResponse,
    PatchAlert,
    PatchChampionInfo,
    SessionFatigue,
    StatsSummary,
    TrendPoint,
    WeeklyReport,
)
from backend.app.services.baselines import serialize_baselines
from backend.app.services import datadragon

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
async def summary(user_id: CurrentUserId) -> StatsSummary:
    """Promedios como números. El monolito devolvía la KDA como el string "5.0 / 2.0 / 10.0",
    que la UI re-parseaba con `.split('/')` — origen del bug de `app.py:128`."""
    return StatsSummary(**await repo.summary(user_id))


@router.get("/champions", response_model=list[ChampionStats])
async def champions(user_id: CurrentUserId) -> list[ChampionStats]:
    """Incluye `winrate` y `kda_ratio` calculados en SQL: las dos columnas que la Tab 3 de
    Streamlit pedía y que la query nunca devolvía."""
    return [ChampionStats(**row) for row in await repo.champion_performance(user_id)]


@router.get("/champion-summary", response_model=list[ChampionRoleSummary])
async def champion_role_summary(user_id: CurrentUserId) -> list[ChampionRoleSummary]:
    """Dónde rindes mejor: winrate/KDA por (campeón, rol, cola) con mínimo de 3 partidas.

    Es el desglose que los stats globales no ven: una caída en el winrate general puede
    venir solo de jugar en una cola de normales o de un rol fuera del pool. `HAVING` en SQL
    descarta las combinaciones con menos de 3 partidas, donde el winrate es ruido.
    """
    return [ChampionRoleSummary(**row) for row in await repo.champion_role_summary(user_id)]


@router.get("/session-fatigue", response_model=SessionFatigue)
async def session_fatigue(user_id: CurrentUserId) -> SessionFatigue:
    """Estado de sesión: compara las últimas 5 partidas con las 5 anteriores.

    Detecta autopilot (caída severa de winrate/KDA entre bloques) para el banner "Estado de
    Sesión" del Dashboard. `sample_ok` es False cuando no hay 10 partidas válidas aún; el
    frontend muestra el `message` informativo igualmente.
    """
    return SessionFatigue(**await repo.session_fatigue(user_id))


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(settings: SettingsDep, user_id: CurrentUserId) -> HeatmapResponse:
    result = await repo.activity_heatmap(settings.display_timezone, user_id)
    cells = [HeatmapCell(**row) for row in result["cells"]]
    best = HeatmapCell(**result["best_slot"]) if result["best_slot"] else None
    worst = HeatmapCell(**result["worst_slot"]) if result["worst_slot"] else None
    return HeatmapResponse(cells=cells, best_slot=best, worst_slot=worst)


@router.get("/patch-alert", response_model=PatchAlert)
async def patch_alert_endpoint(user_id: CurrentUserId) -> PatchAlert:
    """Alerta de parche: caída de winrate del Champion Pool tras una actualización.

    Resuelve el parche actual desde Data Dragon (caché 1h), lo normaliza a "X.Y" y compara
    el winrate de los 3 campeones más jugados en ese parche contra su historial previo.
    `has_current_games` distingue el caso de "parche recién salido sin partidas aún".
    """
    try:
        full_patch = await datadragon.get_current_patch()
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No hay parche de Data Dragon disponible para el análisis.",
        ) from exc

    current_patch = ".".join(full_patch.split(".")[:2])
    result = await repo.patch_alert(user_id, current_patch)

    champions = [PatchChampionInfo(**row) for row in result["champions"]]
    return PatchAlert(
        current_patch=result["current_patch"],
        has_current_games=result["has_current_games"],
        alerting_champions=[c.champion for c in champions if c.dropped],
        champions=champions,
    )


@router.get("/lp-trend")
async def lp_trend(user_id: CurrentUserId, limit: int = 20, queue: int | None = None) -> list[dict]:
    """LP acumulado en orden cronológico. `has_lp` distingue "0 LP" de "aún sin registrar".

    `queue` acota la cola (420 = Solo/Duo): las normales sin LP diluyen la curva si cuentan como 0.
    """
    return await repo.lp_trend(user_id, limit=limit, queue_id=queue)


@router.get("/trends", response_model=list[TrendPoint])
async def kpi_trends(user_id: CurrentUserId, limit: int = 50) -> list[TrendPoint]:
    """Serie temporal de KPIs de mejora (CS/min, DPM, KDA) de las últimas partidas válidas.

    Ignora remakes (< 5 min); los DPM de filas legacy sin participants llegan como 0.
    """
    return [TrendPoint(**row) for row in await repo.kpi_trend(user_id, limit=limit)]


@router.get("/laning", response_model=LaningSummary)
async def laning(user_id: CurrentUserId, limit: int = 50) -> LaningSummary:
    """Triángulo del Laning: promedios GD@15 / XPD@15 / CSD@15 (Timeline de Riot).

    `games_analyzed` dice cuántas de las últimas 50 partidas válidas tenían datos de
    timeline (0 recién instalado, antes del primer sync con la nueva extracción); los
    promedios son None sin ninguna partida.
    """
    return LaningSummary(**await repo.laning_summary(user_id, limit=limit))


@router.get("/weekly", response_model=WeeklyReport)
async def weekly_report(user_id: CurrentUserId) -> WeeklyReport:
    """Resumen de la última semana (7 días, fecha UTC): partidas, winrate, KDA, top campeón
    y mejor partida por rating. `most_played`/`best_match` son null si no hay partidas en la ventana."""
    report = await repo.weekly_report(user_id)
    return WeeklyReport(**report)


@router.get("/meta-verdict", response_model=MetaVerdictResponse)
async def meta_verdict(user_id: CurrentUserId) -> MetaVerdictResponse:
    """Veredicto del meta: winrate por emparejamiento (tú vs enemigo) en el parche actual
    contra el histórico de todos los parches anteriores.

    Es la extensión de la Alerta de Parche a la matriz de matchups: cruza `champion` vs
    `enemy_champion` y separa las partidas de la `game_version` actual del historial previo.
    `meta_shift` marca los emparejamientos que eran favorables (winrate previo >= 55% con
    muestra previa) y ahora caen por debajo del 50% — la alerta de "el meta se te ha dado la
    vuelta" que el frontend resalta en la vista Matchups.
    """
    try:
        full_patch = await datadragon.get_current_patch()
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No hay parche de Data Dragon disponible para el análisis.",
        ) from exc

    current_patch = ".".join(full_patch.split(".")[:2])
    rows = await repo.meta_verdict(user_id, current_patch)
    return MetaVerdictResponse(
        current_patch=current_patch,
        verdicts=[MetaVerdict(**assess_patch_row) for assess_patch_row in rows],
    )


@router.get("/matchups/{user_champion}/{enemy_champion}", response_model=MatchupStats)
async def matchup_stats(user_id: CurrentUserId, user_champion: str, enemy_champion: str) -> MatchupStats:
    """Estadísticas históricas del cruce de dos campeones.

    Filtra por campeón del usuario contra el rival de línea. Con cero partidas devuelve
    todo a 0 (no 404), porque la vista Matchups sigue funcionando con notas aunque no
    haya historial del cruce.
    """
    row = await repo.matchup(user_id, user_champion, enemy_champion)
    return MatchupStats(user_champion=user_champion, enemy_champion=enemy_champion, **row)


@router.get("/baselines", response_model=dict[str, BaselineStats])
async def baselines() -> dict[str, dict[str, float]]:
    """Líneas base por rol: lo 'normal' de CS/min, DPM, KP% y visión para comparar en Full Stats.

    Las mismas cifras que usa el rating (`_ROLE_PROFILES` en riot.py); incluye `"default"` para
    roles desconocidos (ARAM, remakes).
    """
    return serialize_baselines()
