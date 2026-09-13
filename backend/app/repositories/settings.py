"""Configuración persistida del usuario: champion pool y OKRs.

En la v2.0 (migración 013) la tabla es por-usuario: `user_settings (user_id PK)`. Se usa un
upsert en lugar de UPDATE para que la API funcione aunque la fila de ese usuario no exista.
"""

from __future__ import annotations

from typing import Any

from backend.app import db


async def get(user_id: str) -> dict[str, Any]:
    """Devuelve la configuración, creando la fila por defecto si aún no existe."""
    row = await db.fetch_one(
        "SELECT * FROM user_settings WHERE user_id = %s", (user_id,)
    )
    if row is not None:
        return row

    await db.execute(
        "INSERT INTO user_settings (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
        (user_id,),
    )
    row = await db.fetch_one(
        "SELECT * FROM user_settings WHERE user_id = %s", (user_id,)
    )
    if row is None:  # la tabla no existe -> falta aplicar la migración 013
        raise RuntimeError(
            "No se pudo leer user_settings. ¿Aplicaste backend/migrations/013_multiuser_rls.sql?"
        )
    return row


async def replace(
    user_id: str,
    champion_pool: list[str],
    target_cs_min: float,
    max_deaths: float,
    target_dpm: int,
    target_kp_percent: int,
    target_vision_score: int,
) -> dict[str, Any]:
    """Reemplaza la configuración completa de un usuario y devuelve el estado resultante."""
    return await db.fetch_one(  # type: ignore[return-value]
        """
        INSERT INTO user_settings (
            user_id, champion_pool, target_cs_min, max_deaths,
            target_dpm, target_kp_percent, target_vision_score, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (user_id) DO UPDATE SET
            champion_pool      = EXCLUDED.champion_pool,
            target_cs_min      = EXCLUDED.target_cs_min,
            max_deaths         = EXCLUDED.max_deaths,
            target_dpm         = EXCLUDED.target_dpm,
            target_kp_percent  = EXCLUDED.target_kp_percent,
            target_vision_score = EXCLUDED.target_vision_score,
            updated_at         = now()
        RETURNING *
        """,
        (
            user_id,
            champion_pool,
            target_cs_min,
            max_deaths,
            target_dpm,
            target_kp_percent,
            target_vision_score,
        ),
    )


async def update_riot(
    user_id: str, riot_id: str | None, riot_region: str | None = "EUW1"
) -> dict[str, Any]:
    """Vincula (o desvincula, con `riot_id=None`) la cuenta Riot del usuario.

    Actualiza las columnas de la migración 014. UPSERT para que funcione aunque la fila
    del usuario no exista todavía. La región se normaliza a mayúsculas al escribir: las
    claves de `ROUTING_MAP` (config.py) vienen en 'EUW1', 'LA1'...
    """
    return await db.fetch_one(  # type: ignore[return-value]
        """
        INSERT INTO user_settings (user_id, riot_id, riot_region, updated_at)
        VALUES (%s, %s, %s, now())
        ON CONFLICT (user_id) DO UPDATE SET
            riot_id     = EXCLUDED.riot_id,
            riot_region = EXCLUDED.riot_region,
            updated_at  = now()
        RETURNING *
        """,
        (user_id, riot_id, (riot_region or "EUW1").upper()),
    )