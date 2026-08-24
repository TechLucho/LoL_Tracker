"""Observabilidad mínima pero real: request-id correlacionable + latencias p50/p95.

Las tres piezas que la auditoría marcaba como hueco ("un pico de latencia de Supabase es
invisible", "logs de texto plano sin request-ID"):

  1. `request_id_var` — ContextVar con el id de la petición actual. Segura con asyncio: cada
     petición corre en su propio contexto y las tareas hijas (incluido el sync en background,
     que Starlette ejecuta dentro del ciclo request/response) heredan una copia al crearse.
  2. `RequestIdFilter` + `setup_logging()` — el formato del handler raíz imprime el id, así
     que CUALQUIER logger (routers, servicios, librerías) queda correlacionado con su petición.
  3. `LatencyRegistry` — conteo y duraciones por (método, path-template) en memoria, expuesto
     como p50/p95/max en GET /api/metrics.

Deliberadamente NO Prometheus/APM externo: app mono-usuario y mono-proceso; un dict en memoria
sobra y no añade dependencias ni infraestructura.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger(__name__)

# "-" (no vacío) cuando algo loguea fuera de una petición: arranque, tareas del lifespan...
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inyecta el request-id del contexto en cada record que pase por el handler raíz."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    """Handler raíz único con request-id embebido en el formato.

    Uvicorn configura SUS loggers ("uvicorn", "uvicorn.access"...) con handlers propios y
    propagate=False, así que siguen con su formato coloreado; todo lo demás (nuestra app y
    librerías) pasa por aquí.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]


# ─────────────────────────── métricas de latencia ───────────────────────────

# Ventana móvil por endpoint: suficiente para detectar "Supabase está lento hoy" sin crecer
# sin límite en una sesión larga.
_WINDOW = 500


@dataclass
class _EndpointStats:
    count: int = 0
    errors: int = 0
    durations_ms: deque[float] = field(default_factory=lambda: deque(maxlen=_WINDOW))


def _percentile(ordered: list[float], q: float) -> float:
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


class LatencyRegistry:
    """p50/p95/max por endpoint, en memoria. Válido SÓLO mono-proceso (igual que _SyncState)."""

    def __init__(self) -> None:
        self._started_at = time.monotonic()
        self._stats: dict[tuple[str, str], _EndpointStats] = {}

    def observe(self, method: str, path_template: str, duration_ms: float, *, is_error: bool) -> None:
        stats = self._stats.setdefault((method, path_template), _EndpointStats())
        stats.count += 1
        if is_error:
            stats.errors += 1
        stats.durations_ms.append(duration_ms)

    def snapshot(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for (method, path), s in sorted(self._stats.items()):
            ordered = sorted(s.durations_ms)
            out.append({
                "method": method,
                "path": path,
                "count": s.count,
                "errors": s.errors,
                "p50_ms": round(_percentile(ordered, 0.5), 1),
                "p95_ms": round(_percentile(ordered, 0.95), 1),
                "max_ms": round(ordered[-1] if ordered else 0.0, 1),
            })
        return out

    def uptime_seconds(self) -> int:
        return int(time.monotonic() - self._started_at)


latency_registry = LatencyRegistry()


def _path_template(request: Request) -> str:
    """Plantilla de ruta ("/api/matches/{game_id}") para no explotar la cardinalidad por id.

    Starlette la deja en scope["route"] tras el routing; si no hubo match (404) caemos al
    path literal — aceptable en mono-usuario.
    """
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


async def observability_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """request-id + X-Request-ID + latencia por petición.

    El ContextVar se fija ANTES de call_next: así heredan hacia abajo los endpoints Y las
    BackgroundTasks (el sync en segundo plano loguea con el mismo id). El reset posterior no
    afecta a tareas ya creadas: capturaron su copia del contexto al nacer.

    En un 500 por excepción la cabecera no llega (la renderiza ServerErrorMiddleware por
    fuera de este middleware), pero el log del error sí lleva el id para trazarlo.
    """
    rid = uuid.uuid4().hex
    token = request_id_var.set(rid)
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        latency_registry.observe(
            request.method, _path_template(request), elapsed_ms, is_error=True
        )
        log.exception(
            "%s %s -> EXCEPCIÓN (%.1f ms)", request.method, request.url.path, elapsed_ms
        )
        request_id_var.reset(token)
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = rid
    latency_registry.observe(
        request.method,
        _path_template(request),
        elapsed_ms,
        is_error=response.status_code >= 500,
    )
    # Línea de acceso propia: uvicorn.access no lleva request-id; esta sí permite grep por id.
    log.info(
        "%s %s -> %d (%.1f ms)",
        request.method, request.url.path, response.status_code, elapsed_ms,
    )
    request_id_var.reset(token)
    return response
