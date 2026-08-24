"""Configuración persistida del usuario: champion pool y OKRs.

Tabla de una sola fila (`id = 1`). Se usa un upsert en lugar de UPDATE para que la API funcione
aunque la fila semilla de la migración 003 no exista.
"""

from __future__ import annotations

from typing import Any

from backend.app import db


async def get() -> dict[str, Any]:
    """Devuelve la configuración, creando la fila por defecto si aún no existe."""
    row = await db.fetch_one("SELECT * FROM user_settings WHERE id = 1")
    if row is not None:
        return row

    await db.execute("INSERT INTO user_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
    row = await db.fetch_one("SELECT * FROM user_settings WHERE id = 1")
    if row is None:  # la tabla no existe -> falta aplicar la migración 003
        raise RuntimeError(
            "No se pudo leer user_settings. ¿Aplicaste backend/migrations/003_user_settings.sql?"
        )
    return row


async def replace(
    champion_pool: list[str], target_cs_min: float, max_deaths: float
) -> dict[str, Any]:
    """Reemplaza la configuración completa y devuelve el estado resultante."""
    return await db.fetch_one(  # type: ignore[return-value]
        """
        INSERT INTO user_settings (id, champion_pool, target_cs_min, max_deaths, updated_at)
        VALUES (1, %s, %s, %s, now())
        ON CONFLICT (id) DO UPDATE SET
            champion_pool = EXCLUDED.champion_pool,
            target_cs_min = EXCLUDED.target_cs_min,
            max_deaths    = EXCLUDED.max_deaths,
            updated_at    = now()
        RETURNING *
        """,
        (champion_pool, target_cs_min, max_deaths),
    )
