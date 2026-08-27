"""Migration runner idempotente.

Uso:
    python -m backend.scripts.migrate          # aplica pendientes usando DB de .env
    DATABASE_URL=... python -m backend.scripts.migrate  # DB explícita

Crea la tabla interna `_schema_migrations` si no existe, lee los archivos `.sql` de
`backend/migrations/` en orden alfabético, ejecuta solo los que no estén registrados y
marca cada uno como aplicado. Idempotente: ejecutarlo N veces produce el mismo resultado.

Las migraciones son transaccionales: si un `.sql` falla, se revierte esa migración y el
runner se detiene (los posteriores quedan pendientes para la próxima ejecución).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg

log = logging.getLogger("migrate")

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

# SQL para bootstrap de la tabla de control.
_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS _schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_CHECK_EXISTS = "SELECT 1 FROM _schema_migrations WHERE filename = %s"
_REGISTER = "INSERT INTO _schema_migrations (filename) VALUES (%s)"


def _dsn_from_env() -> str:
    """Construye un DSN de libpq desde las mismas variables que config.py.

    Si existe DATABASE_URL (CI, scripts), se usa directamente. En caso contrario,
    reconstruye el DSN pieza por pieza para ser consistente con Settings.dsn.
    """
    if url := os.environ.get("DATABASE_URL"):
        return url

    parts = {
        "host": os.environ["DB_HOST"],
        "port": os.environ.get("DB_PORT", "5432"),
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "sslmode": os.environ.get("DB_SSLMODE", "require"),
    }
    return " ".join(f"{k}={v}" for k, v in parts.items())


def _discover_migrations() -> list[Path]:
    """Devuelve los archivos .sql ordenados alfabéticamente."""
    if not MIGRATIONS_DIR.is_dir():
        log.warning("Directorio de migraciones no encontrado: %s", MIGRATIONS_DIR)
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run(dsn: str | None = None) -> int:
    """Aplica migraciones pendientes. Devuelve el número de migraciones ejecutadas."""
    if dsn is None:
        dsn = _dsn_from_env()

    applied = 0
    with psycopg.connect(dsn) as conn:
        # Asegurar que la tabla de control existe.
        conn.execute(_CREATE_MIGRATIONS_TABLE)

        for path in _discover_migrations():
            filename = path.name

            # ¿Ya aplicada?
            already = conn.execute(_CHECK_EXISTS, (filename,)).fetchone()
            if already:
                log.debug("Ya aplicada, omitiendo: %s", filename)
                continue

            sql = path.read_text(encoding="utf-8")
            log.info("Aplicando migración: %s", filename)

            # Cada migración corre en su propia transacción implícita (autocommit off
            # pero el execute de psycopg3 hace commit por defecto). Para rollback
            # parcial, usar un savepoint.
            with conn.cursor() as cur:
                cur.execute("SAVEPOINT migration")
                try:
                    cur.execute(sql)
                except Exception:
                    cur.execute("ROLLBACK TO SAVEPOINT migration")
                    log.exception("Fallo al aplicar %s — revertida esa migración", filename)
                    raise
                else:
                    cur.execute("RELEASE SAVEPOINT migration")
                    cur.execute(_REGISTER, (filename,))
                    conn.commit()
                    applied += 1
                    log.info("OK: %s aplicada", filename)

    log.info("Migraciones aplicadas: %d", applied)
    return applied


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    try:
        n = run()
    except KeyError as exc:
        log.error("Variable de entorno faltante: %s", exc)
        sys.exit(1)
    except psycopg.OperationalError as exc:
        log.error("No se pudo conectar a la base de datos: %s", exc)
        sys.exit(1)
    except Exception:
        log.exception("Error inesperado durante la migración")
        sys.exit(1)

    if n == 0:
        log.info("Base de datos al día — nada que hacer.")


if __name__ == "__main__":
    main()
