"""Métricas de latencia/errores en memoria (p50/p95/max por endpoint).

Es el "nivel mínimo" que proponía la auditoría: un dict en memoria alimentado por el
middleware de observabilidad, expuesto para poder VER un pico de latencia de Supabase sin
montar Prometheus. Suficiente para mono-usuario; si algún día hay multi-proceso, esto y
_SyncState romperían juntos (y el arranque lo impide).
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.observability import latency_registry
from backend.app.schemas import EndpointMetric, MetricsSnapshot

router = APIRouter(prefix="/api/metrics", tags=["observability"])


@router.get("", response_model=MetricsSnapshot)
async def metrics() -> MetricsSnapshot:
    return MetricsSnapshot(
        uptime_seconds=latency_registry.uptime_seconds(),
        endpoints=[EndpointMetric(**e) for e in latency_registry.snapshot()],
    )
