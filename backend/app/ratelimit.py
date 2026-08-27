"""Rate limiter en memoria para app mono-usuario.

Diccionario sliding-window: cada clave (token o IP) mantiene una lista de timestamps.
Si la ventana supera MAX_REQUESTS por WINDOW_SECONDS, se devuelve 429. La limpieza
de entradas antiguas ocurre en cada check (amortizado): en mono-usuario el diccionario
nunca crece, así que no hay riesgo de memory leak.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

WINDOW_SECONDS = 60
MAX_REQUESTS = 100


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware HTTP: cuenta peticiones por clave y rechaza con 429 si se excede."""

    def __init__(self, app: ASGIApp, max_requests: int = MAX_REQUESTS, window: int = WINDOW_SECONDS) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_key(self, request: Request) -> str:
        """Clave de rate-limit: el token del header si existe, si no la IP."""
        token = request.headers.get("x-api-token")
        if token:
            return f"token:{token}"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Solo limitamos rutas protegidas (/api/*), no /health ni docs.
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        window_start = now - self.window

        # Limpiar timestamps fuera de la ventana
        hits = self._hits[key]
        self._hits[key] = [t for t in hits if t > window_start]

        if len(self._hits[key]) >= self.max_requests:
            return Response(
                content='{"detail":"Demasiadas peticiones. Intenta de nuevo en un minuto."}',
                status_code=429,
                media_type="application/json",
            )

        self._hits[key].append(now)
        return await call_next(request)
