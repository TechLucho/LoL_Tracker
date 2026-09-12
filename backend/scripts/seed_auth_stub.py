"""Dev/CI: siembra el stub de `auth.*` en un Postgres efímero — NUNCA en Supabase.

`auth.users`, `auth.uid()` y el resto del schema `auth` son territorio de Supabase: la
aplicación no puede crearlos ni alterarlos ahí (el intento anterior rompió la migración con
`InsufficientPrivilege: permission denied for schema auth`). Pero el CI y los Postgres efímeros
de desarrollo arrancan como `postgres:16` pelado, sin las herramientas de Supabase, y la
migración 013 referencia `auth.users` (FK) y `auth.uid()` (políticas RLS). Este script crea un
stub mínimo ESOS solos entornos, ANTES de aplicar migraciones:

    python -m backend.scripts.seed_auth_stub   # luego python -m backend.scripts.migrate

Idempotente: `SCHEMA IF NOT EXISTS` / `TABLE IF NOT EXISTS` / guard en la función. En una DB de
Supabase no hay que ejecutarlo jamás (y aún si se hiciera, Supabase lo rechaza con el mismo
InsufficientPrivilege). Requiere las mismas credenciales que el runner de migraciones
(migrate._dsn_from_env).
"""
from __future__ import annotations

import logging
import sys

import psycopg
from dotenv import load_dotenv

from backend.scripts.migrate import _dsn_from_env

load_dotenv()

log = logging.getLogger("seed_auth_stub")

# DDL del mock. Los $tags$ de dollar-quoting son distintos entre sí a propósito: uno
# anidado (como el malogrado `AS $$ ... $$` dentro de `DO $$`) cerraría el bloque antes de
# tiempo y rompería el parseo. El `EXECUTE` es obligatorio para DDL dentro de plpgsql.
AUTH_STUB_SQL = """
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY
);

DO $auth_stub$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth' AND p.proname = 'uid'
    ) THEN
        EXECUTE $auth_uid$
            CREATE FUNCTION auth.uid() RETURNS uuid
            LANGUAGE sql
            AS $body$ SELECT NULL::uuid; $body$
        $auth_uid$;
    END IF;
END $auth_stub$;
"""


def ensure_auth_stub(dsn: str, *, commit: bool = True) -> None:
    """Aplica AUTH_STUB_SQL. Idempotente; útil también desde los tests de integración."""
    with psycopg.connect(dsn) as conn:
        conn.execute(AUTH_STUB_SQL)
        if commit:
            conn.commit()


def main() -> int:
    """Siembra el stub y devuelve 0 si OK."""
    dsn = _dsn_from_env()
    try:
        ensure_auth_stub(dsn)
    except psycopg.OperationalError as exc:
        log.error("No se pudo conectar a la base de datos: %s", exc)
        return 1
    except Exception:  # noqa: BLE001
        log.exception("No se pudo sembrar el stub de auth")
        return 1

    log.info("Stub de auth.* listo (schema + auth.users + auth.uid())")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    sys.exit(main())