"""Dev: vacía las tablas transaccionales antes de aplicar la migración 013.

La columna `user_id` entra en 013 como `UUID NOT NULL` sin valor por defecto. Si la tabla tiene
filas, `ALTER TABLE ... ADD COLUMN ... NOT NULL` falla con "column ... contains null values". En
desarrollo local un TRUNCATE previo es aceptable — la migración a multi-usuario exige "abandonar"
el historial de una sola persona (el dato sigue siendo tuyo, pero en la v2.0 pasa a vivir bajo tu
user_id y el schema ya no lo puede repartir por él).

NO toca `scout_cache` ni los historiales de metadatos: siguen siendo globales (la caché del
escout se comparte entre usuarios para no duplicar llamadas a la API de Riot).

Requiere las mismas credenciales de DB que el runner de migraciones (migrate._dsn_from_env).

Uso:
    python -m backend.scripts.truncate_tables   # TRUNCATE ... CASCADE de las 5 tablas
"""
from __future__ import annotations

import logging
import sys

import psycopg
from dotenv import load_dotenv

from backend.scripts.migrate import _dsn_from_env

load_dotenv()

log = logging.getLogger("truncate")

# Las 5 tablas que pasan a ser por-usuario en la migración 013. scout_cache y metadatos NO.
TRANSACTIONAL_TABLES = ("matches", "user_settings", "sync_runs", "matchup_notes", "lp_snapshots")


def main() -> int:
    """Ejecuta `TRUNCATE ... CASCADE` sobre las tablas transaccionales. Devuelve 0 si OK."""
    dsn = _dsn_from_env()
    table_sql = ", ".join(TRANSACTIONAL_TABLES)
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute(f"TRUNCATE {table_sql} CASCADE")
            conn.commit()
    except psycopg.OperationalError as exc:
        log.error("No se pudo conectar a la base de datos: %s", exc)
        return 1
    except Exception:  # noqa: BLE001
        log.exception("TRUNCATE falló")
        return 1

    log.info("TRUNCATE OK: %s", ", ".join(TRANSACTIONAL_TABLES))
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    sys.exit(main())