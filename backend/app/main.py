"""Punto de entrada de la API.

Arranque:
    python -m uvicorn backend.app.main:app --reload
Docs interactivas:
    http://localhost:8000/docs

IMPORTANTE (operación): la app es MONO-PROCESO por diseño — el estado del sync (_SyncState)
y las métricas de latencia viven en memoria del proceso. El lifespan lo verifica y se niega
a arrancar con múltiples workers: con N workers el polling de /api/sync/status daría
resultados distintos según quién atienda cada petición. Escalar verticalmente, no en procesos.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.app import db
from backend.app.config import get_settings
from backend.app.deps import require_token
from backend.app.observability import (
    observability_middleware,
    setup_logging,
)
from backend.app.routers import (
    config,
    constitution,
    health,
    matches,
    metadata,
    metrics,
    scout,
    stats,
    sync,
)

setup_logging()
log = logging.getLogger(__name__)


def _assert_single_process() -> None:
    """Falla rápido si se detecta configuración multi-worker.

    Señales vigiladas: `--workers`/`-w` de uvicorn/gunicorn en argv y `UVICORN_WORKERS`/
    `WEB_CONCURRENCY` en el entorno (las convenciones que usan PaaS y Docker). Un falso
    negativo exótico es preferible a bloquear arranques legítimos; un multi-worker silencioso
    NO es aceptable porque corrompe el polling del sync de forma intermitente.
    """
    offenders: list[str] = []

    argv = sys.argv
    for i, arg in enumerate(argv):
        # Formas separada y con "=" que aceptan tanto uvicorn como gunicorn.
        if arg in ("--workers", "-w"):
            value = argv[i + 1] if i + 1 < len(argv) else ""
            if value.isdigit() and int(value) > 1:
                offenders.append(f"{arg} {value}")
        elif arg.startswith("--workers=") or arg.startswith("-w="):
            value = arg.split("=", 1)[1]
            if value.isdigit() and int(value) > 1:
                offenders.append(arg)

    for var in ("UVICORN_WORKERS", "WEB_CONCURRENCY"):
        raw = os.environ.get(var, "")
        if raw.isdigit() and int(raw) > 1:
            offenders.append(f"{var}={raw}")

    if offenders:
        raise RuntimeError(
            "LoL Tracker es mono-proceso por diseño: _SyncState (sync en background) y las "
            "métricas de latencia viven en la memoria del proceso. Con varios workers el "
            f"polling de /api/sync/status daría resultados según el worker que atienda. "
            f"Detectado: {', '.join(offenders)}. Arranca con UN solo worker "
            "(sin --workers, WEB_CONCURRENCY=1)."
        )
    log.info("Restricción mono-proceso verificada (un único worker)")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """El pool se abre UNA vez por proceso.

    Esto es la diferencia de fondo con Streamlit: allí cada re-ejecución del script abría ~10
    conexiones nuevas a Supabase por interacción.
    """
    _assert_single_process()
    _hint_windows_event_loop()
    settings = get_settings()
    try:
        await db.open_pool()
        log.info("Pool abierto contra %s (tz de visualización: %s)",
                 settings.db_host, settings.display_timezone)
    except Exception as exc:  # noqa: BLE001
        # Arrancar en modo degradado a propósito: así /health puede explicar qué falta en vez de
        # que el proceso muera sin dejar rastro útil.
        log.error("No se pudo abrir el pool: %s", exc)
    try:
        yield
    finally:
        await db.close_pool()
        log.info("Pool cerrado")


def _hint_windows_event_loop() -> None:
    """Aviso temprano si el loop actual va a dejar a psycopg sin conexión.

    Psycopg en modo async exige un selector-loop; en Windows, `uvicorn` SIN `--reload` usa el
    ProactorEventLoop por defecto y cada intento de conexión falla con una ráfaga de warnings
    crípticos del pool. No se puede cambiar el policy a estas alturas (el loop ya está corriendo),
    así que lo honesto es avisar YA y decir cómo arrancar bien. En Linux/Docker esto no aplica.
    """
    if sys.platform != "win32":
        return
    import asyncio

    if type(asyncio.get_running_loop()) is asyncio.ProactorEventLoop:
        log.warning(
            "ProactorEventLoop detectado: psycopg async NO podrá conectar (pool en modo "
            "degradado). En Windows arranca con --reload (fuerza SelectorEventLoop) o bajo "
            "Linux/Docker para producción."
        )


settings = get_settings()

app = FastAPI(
    title="LoL Tracker API",
    description="Backend del dashboard de rendimiento en ranked. Sustituye al monolito Streamlit.",
    version="2.0.0-dev",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def http_observability(request: Request, call_next) -> Response:
    """request-id por petición (cabecera X-Request-ID + logs), latencia p50/p95 en memoria."""
    return await observability_middleware(request, call_next)


# /health queda sin auth para poder diagnosticar credenciales sin credenciales.
app.include_router(health.router)

_protected = [Depends(require_token)]
# Alias autenticado /api/health: mismo handler que /health, montado bajo el prefijo que usa el
# cliente axios del frontend (baseURL termina en /api). Protegido como el resto de /api/*.
app.include_router(health.router, prefix="/api", dependencies=_protected)
app.include_router(matches.router, dependencies=_protected)
app.include_router(stats.router, dependencies=_protected)
app.include_router(scout.router, dependencies=_protected)
app.include_router(sync.router, dependencies=_protected)
app.include_router(config.router, dependencies=_protected)
app.include_router(constitution.router, dependencies=_protected)
app.include_router(metadata.router, dependencies=_protected)
app.include_router(metrics.router, dependencies=_protected)
