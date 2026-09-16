"""Tests de integración de repositories/ contra Postgres REAL.

La auditoría crítica señalaba que ninguna query SQL estaba cubierta por CI: aquí se ejercitan
`insert_many`, `list_recent`, `last_results`, `champion_performance` y `lp_trend`
contra un Postgres de verdad con el esquema de `backend/migrations/*.sql` ya aplicado.

Requisitos:
  * `TEST_DATABASE_URL` en el entorno (el workflow del CI la exporta y aplica las migraciones
    antes de pytest).
  * La migración 013 deja que SUPABASE sea el dueño de `auth.users`/`auth.uid()` (el schema
    `auth` bloquea escrituras de la aplicación). El Postgres efímero de tests no tiene Supabase,
    así que el stub previo lo pone, ANTES de migrar, `python -m backend.scripts.seed_auth_stub`
    (en CI es el paso "Seed auth stub"; manualmente, el mismo comando). Este `conftest` añade un
    fixture autouse que garantiza ese stub sobre la DB de tests — red de seguridad para runs
    locales con TEST_DATABASE_URL que saltaron el paso.
  * Si la DB no lleva TLS (postgres efímero local/CI), exportar también `DB_SSLMODE=disable`;
    los repos abren el pool vía config.Settings, que por defecto exige TLS (Supabase).

Sin `TEST_DATABASE_URL` toda la carpeta se ignora: en local sin Postgres, la suite hermética
sigue siendo el comportamiento por defecto y no hay intentos de conexión colgados.
"""

from __future__ import annotations

import os
import pathlib

import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    collect_ignore = [p.name for p in pathlib.Path(__file__).parent.glob("test_*.py")]


@pytest.fixture(scope="session", autouse=True)
def _ensure_auth_stub():
    """Crea (si falta) el stub de `auth.*` sobre la DB de tests. Idempotente.

    En CI el stub ya lo sembró el workflow antes de las migraciones; este fixture cubre los
    runs locales con TEST_DATABASE_URL sobre un efímero que no pasó por ese paso, y deja
    `auth.users` lista para que los escenarios siembren sus `user_id`. Sobre Supabase jamás
    se ejecuta (sin TEST_DATABASE_URL no hay tests de integración recogidos).
    """
    if not os.environ.get("TEST_DATABASE_URL"):
        return

    from backend.scripts.migrate import _dsn_from_env
    from backend.scripts.seed_auth_stub import ensure_auth_stub

    ensure_auth_stub(_dsn_from_env())