"""Pool de conexiones a Supabase.

Esto es la corrección directa del problema que nos hizo abandonar Streamlit: allí cada sección
de la UI abría su propia conexión (~10 handshakes TCP+TLS por clic, cada uno con un
CREATE TABLE IF NOT EXISTS redundante). Aquí el pool se abre una vez en el lifespan de FastAPI
y se reutiliza; el esquema se gestiona con migraciones versionadas, no en runtime.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from backend.app.config import get_settings

_pool: AsyncConnectionPool | None = None


async def open_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            conninfo=settings.dsn,
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
            open=False,
            timeout=15.0,
        )
        await _pool.open(wait=True, timeout=20.0)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("El pool no está abierto. ¿Falta el lifespan de la app?")
    return _pool


@asynccontextmanager
async def cursor() -> AsyncIterator[Any]:
    """Cursor con filas como dicts. Commit al salir, rollback si algo revienta."""
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            yield cur


async def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with cursor() as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    async with cursor() as cur:
        await cur.execute(query, params)
        return await cur.fetchone()


async def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    """Ejecuta una escritura y devuelve el número de filas afectadas."""
    async with cursor() as cur:
        await cur.execute(query, params)
        return cur.rowcount
