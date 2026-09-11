"""Sincronización con Riot, en segundo plano.

El sync puede tardar minutos (N partidas × reintentos con backoff respetando Retry-After).
Antes la petición HTTP esperaba a todo el proceso y el frontend quedaba colgado del timeout;
ahora el POST sólo valida y encola (202 Accepted), y el progreso se consulta en
GET /api/sync/status.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from backend.app.deps import RiotServiceDep, SettingsDep
from backend.app.repositories import lp as lp_repo
from backend.app.repositories import matches as repo
from backend.app.repositories import sync_runs
from backend.app.schemas import LpCapture, SyncAccepted, SyncError, SyncResult, SyncStatus
from backend.app.services.riot import FailedMatch, RiotDegradedError, RiotService, RiotServiceError

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["sync"])

DEFAULT_QUEUES = [420, 400]
# Micro-lote del checkpoint incremental: cada N partidas descargadas se persisten al vuelo.
# Si Riot se cae a mitad de un sync largo, lo ya guardado NO se pierde.
SYNC_CHECKPOINT_BATCH = 5


class _SyncState:
    """Estado del sync en curso / último terminado.

    App mono-usuario y mono-proceso: no necesita Redis ni tabla de jobs; un objeto en memoria
    es suficiente y sobrevive mientras viva el proceso de uvicorn.
    """

    def __init__(self) -> None:
        self.status: Literal["idle", "processing", "success", "partial", "error"] = "idle"
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.result: SyncResult | None = None
        self.error: str | None = None


_state = _SyncState()


async def _capture_ranked_lp(riot: RiotService, riot_id: str) -> LpCapture | None:
    """Auto-tracker de LP: snapshot League-V4 + delta sobre la última partida sin review.

    Estrategia (migración 005): Riot ya no expone LP por partida, así que comparamos el
    snapshot actual con el anterior y escribimos el delta neto como `lp_change` de la partida
    Solo/Duo más reciente SIN review manual y posterior al snapshot previo. Si un sync trae
    varias partidas nuevas, las intermedias quedan con lp_change NULL (la gráfica acumulada
    sigue siendo correcta). Nunca se sobrescribe una review del usuario.

    Errores contenidos: que League-V4 falle (rate limit, key caducada, tabla 005 sin aplicar)
    NO debe convertir un sync exitoso en error — sólo se registra y `lp_captured` queda None.
    """
    try:
        entry = await riot.fetch_ranked_solo_entry(riot_id)
        if entry is None:  # sin clasificación en Solo/Duo
            return None

        delta: int | None = None
        prev = await lp_repo.latest_snapshot(riot_id)
        if prev is not None and prev["lp"] != entry["lp"]:
            game_id = await repo.newest_unreviewed_ranked(after=prev["captured_at"])
            if game_id is not None and await repo.update_details(game_id, {"lp_change": entry["lp"] - prev["lp"]}):
                delta = entry["lp"] - prev["lp"]
                log.info("LP %s%d asignado a %s", "+" if delta > 0 else "", delta, game_id)

        await lp_repo.insert_snapshot(
            riot_id,
            lp=entry["lp"], tier=entry["tier"], division=entry["division"],
            wins=entry["wins"], losses=entry["losses"],
        )
        return LpCapture(lp=entry["lp"], tier=entry["tier"],
                         division=entry["division"], delta_assigned=delta)
    except RiotServiceError as exc:
        log.warning("LP no capturado (Riot): %s", exc)
    except Exception:  # noqa: BLE001
        log.exception("LP no capturado (error inesperado)")
    return None


async def _notify_discord(
    webhook_url: str, status: str, matches_added: int, losing_streak: bool = False
) -> None:
    """POST asíncrono de un embed de resumen al canal de Discord.

    Es un "log externo" pasivo: cualquier error de red se silencia. Un webhook caído no debe
    convertir un sync exitoso en error. Con `losing_streak` el embed se fuerza en rojo (color
    de error) e incluye el aviso de La Constitución.
    """
    color = 0xE63946 if (status != "success" or losing_streak) else 0x9D4EDD
    fields = []
    if losing_streak:
        fields.append(
            {
                "name": "🚨 Racha de derrotas detectada",
                "value": "3+ derrotas consecutivas. Considera aplicar la Constitución y para de jugar.",
                "inline": False,
            }
        )
    payload = {
        "embeds": [
            {
                "title": "Sync completado" + (" ⚠️" if losing_streak else ""),
                "description": f"Estado: **{status}**\nPartidas añadidas: **{matches_added}**",
                "color": color,
                "fields": fields,
            }
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(webhook_url, json=payload)
            res.raise_for_status()
    except Exception:  # noqa: BLE001
        log.warning("Notificación a Discord falló (se ignora)")


async def _run_sync(riot: RiotService, target: str, limit: int, queue_ids: list[int],
                     *, run_id: int, discord_webhook_url: str | None = None) -> None:
    """Cuerpo del sync. Corre como BackgroundTask: NUNCA debe lanzar una excepción sin
    capturar, porque moriría en silencio y el frontend se quedaría sondeando 'processing'.

    Guarda progreso incremental desde el primer micro-lote (SYNC_CHECKPOINT_BATCH partidas) en
    vez de acumular todo en memoria y hacer un único insert al final. Si Riot se degrada a
    mitad de camino (RiotDegradedError: 429 con Retry-After largo o 5xx sostenidos), el sync
    termina en 'partial' con degraded_api=True: lo ya descargado persiste y un nuevo POST
    reanuda sin duplicar (insert_many es idempotente). Sólo un sync completo reevalúa LP y
    Tilt Alert.

    Persiste el resultado final en sync_runs (tabla de auditoría, migración 006). El
    _SyncState en memoria se sigue actualizando para el polling rápido del frontend.
    """
    inserted = 0
    error_msg: str | None = None
    losing_streak = False
    degraded: bool = False
    pending: list[dict] = []
    seen: set[str] = set()
    all_failures: list[FailedMatch] = []

    async def _flush() -> None:
        nonlocal inserted
        if pending:
            inserted += await repo.insert_many(pending)
            pending.clear()

    async def _checkpoint(match: dict) -> None:
        pending.append(match)
        gid = match.get("game_id", "")
        if gid:
            seen.add(gid)
        if len(pending) >= SYNC_CHECKPOINT_BATCH:
            await _flush()

    try:
        for qid in queue_ids:
            try:
                matches, q_failures = await riot.fetch_recent_matches(
                    target, limit=limit, queue=qid, on_match=_checkpoint,
                )
                all_failures.extend(q_failures)
            except RiotDegradedError as exc:
                degraded = True
                error_msg = f"Riot degradado: {exc}"
                log.warning("Sync %s interrumpido por Riot degradado (progreso parcial): %s",
                            target, exc)
                break
            finally:
                # Drena el micro-lote pendiente de esta cola (nunca quedan >=5 en vuelo).
                await _flush()

        fetched = len(seen)
        log.info("Sync %s: %d únicas, %d insertadas, %d fallos (degraded=%s)",
                 target, fetched, inserted, len(all_failures), degraded)
        sync_errors = [
            SyncError(game_id=f.game_id, reason=f.reason, retryable=f.retryable)
            for f in all_failures
        ]

        if degraded:
            # No es un 500: el sync "funcionó" hasta donde Riot dejó. Lo que quedó guardado
            # persiste y el frontend avisa de que hay que reintentar más tarde.
            _state.result = SyncResult(
                fetched=fetched, inserted=inserted, skipped=fetched - inserted,
                errors=sync_errors, degraded_api=True,
            )
            _state.status = "partial"
        else:
            # Auto-tracker de LP: sólo tiene sentido si entraron partidas nuevas de Solo/Duo.
            lp_captured = None
            if inserted > 0 and 420 in queue_ids:
                lp_captured = await _capture_ranked_lp(riot, target)

            # Tilt Alert: si las últimas 3 partidas válidas (Ranked, anti-remake) son derrotas
            # consecutivas, el sync avisa. Se evalúa SIEMPRE (no sólo con insertadas): así un
            # resync manual durante una racha en curso vuelve a recordar que hay que parar.
            recent = await repo.last_results(limit=3)
            losing_streak = len(recent) >= 3 and all(not r["win"] for r in recent)
            if losing_streak:
                log.warning("Tilt Alert: %s lleva 3+ derrotas consecutivas", target)

            _state.result = SyncResult(
                fetched=fetched,
                inserted=inserted,
                skipped=fetched - inserted,
                errors=sync_errors,
                lp_captured=lp_captured,
                losing_streak_warning=losing_streak,
            )
            _state.status = "success"
    except RiotServiceError as exc:
        log.error("Sync falló: %s", exc)
        error_msg = str(exc)
        _state.error = error_msg
        _state.status = "error"
    except Exception as exc:  # noqa: BLE001
        log.exception("Sync falló con excepción inesperada")
        error_msg = f"Error inesperado: {exc}"
        _state.error = error_msg
        _state.status = "error"
    finally:
        _state.finished_at = datetime.now(UTC)
        await sync_runs.finish_run(
            run_id,
            status=_state.status,
            finished_at=_state.finished_at,
            matches_added=inserted,
            error_message=error_msg,
        )
        if discord_webhook_url:
            await _notify_discord(discord_webhook_url, _state.status, inserted, losing_streak)


@router.post("", response_model=SyncAccepted, status_code=202)
async def sync(
    background_tasks: BackgroundTasks,
    riot: RiotServiceDep,
    settings: SettingsDep,
    riot_id: str | None = Query(None, description="Por defecto, el RIOT_ID del .env"),
    limit: int = Query(10, ge=1, le=100),
    queues: str = Query(
        ",".join(str(q) for q in DEFAULT_QUEUES),
        description="IDs de cola separados por coma (420=Solo/Duo, 400=Normal Draft). Default: ambos.",
    ),
) -> SyncAccepted:
    """Encola la sincronización y responde al instante (202).

    La validación (Riot ID, colas) sigue siendo síncrona: los errores de petición se reportan
    aquí, no en el polling. Los fallos de Riot/DB viajan después por `/status`.
    """
    if _state.status == "processing":
        raise HTTPException(409, "Ya hay una sincronización en curso.")

    target = riot_id or settings.riot_id
    if not target:
        raise HTTPException(422, "Falta el Riot ID (ni en la query ni en RIOT_ID del .env).")

    queue_ids: list[int] = []
    for part in queues.split(","):
        part = part.strip()
        if part.isdigit():
            queue_ids.append(int(part))
    if not queue_ids:
        queue_ids = list(DEFAULT_QUEUES)

    _state.started_at = datetime.now(UTC)
    _state.finished_at = None
    _state.result = None
    _state.error = None
    # Guard cerrado: el estado se marca "processing" ANTES de esperar nada (no hay await entre
    # el guard del 409 y esta línea), así dos POST simultáneos nunca atraviesan el guard a la
    # vez (race auditado en v1.6: el viejo orden permitía lanzar dos _run_sync). Si start_run
    # falla (p.ej. la DB está caída), se restaura "idle" y el sync no queda pegado en 409.
    _state.status = "processing"
    try:
        run_id = await sync_runs.start_run(_state.started_at)
    except Exception:
        _state.status = "idle"
        raise
    background_tasks.add_task(_run_sync, riot, target, limit, queue_ids, run_id=run_id,
                              discord_webhook_url=settings.discord_webhook_url)

    return SyncAccepted(
        status="processing",
        message="Sincronización en segundo plano iniciada. Consulta GET /api/sync/status.",
    )


@router.get("/status", response_model=SyncStatus)
async def sync_status() -> SyncStatus:
    """Estado del sync para el polling del frontend (idle/processing/success/partial/error)."""
    return SyncStatus(
        status=_state.status,
        started_at=_state.started_at,
        finished_at=_state.finished_at,
        result=_state.result,
        error=_state.error,
    )
