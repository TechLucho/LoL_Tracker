"""Credenciales para los tests, según el entorno.

* CI (GitHub Actions): el workflow levanta un servicio `postgres:16` efímero en
  localhost:5432 y aplica las migraciones ANTES de pytest. Con `CI=true` los stubs apuntan
  ahí en vez de a credenciales falsas: los smoke tests ven una DB sana ("ok") y la carpeta
  integration/ ejercita repositories/ contra SQL real. `DB_SSLMODE=disable` porque el
  servicio efímero no lleva TLS; el default productivo sigue siendo require (config.py).

* Local sin .env: stubs herméticos como siempre. Ningún test toca la red real; el pool
  arranca en modo degradado y /health lo reporta, que es justo lo que asumen los smoke
  tests. Los tests de integración se auto-saltan sin TEST_DATABASE_URL.

setdefault, no assign: variables ya presentes en el entorno ganan siempre.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid

import jwt
import pytest

os.environ.setdefault("RIOT_API_KEY", "RGAPI-00000000-0000-0000-0000-000000000000")

if os.environ.get("CI", "").lower() == "true":
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_NAME", "lol_tracker_test")
    os.environ.setdefault("DB_USER", "postgres")
    os.environ.setdefault("DB_PASSWORD", "postgres")
    os.environ.setdefault("DB_SSLMODE", "disable")
else:
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_NAME", "lol_tracker_test")
    os.environ.setdefault("DB_USER", "postgres.test")
    os.environ.setdefault("DB_PASSWORD", "test-password")


# Identidad sintética usada por los tests: firma los tokens con el secreto de Settings
# (default de prueba si .env no define SUPABASE_JWT_SECRET; el real si lo define: el token
# siempre cuadra con lo que la app decodifica).
TEST_USER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def make_auth_headers(
    sub: uuid.UUID | str = TEST_USER_UUID,
    *,
    expires_delta: dt.timedelta | None = None,
) -> dict[str, str]:
    """Genera un JWT de Supabase válido y lo empaqueta como header `Authorization: Bearer`.

    Claims mínimos fieles a una sesión real de Supabase (`aud`/`role`/`iat`/`exp` + `sub`).
    Devolver `expires_delta=timedelta(seconds=-60)` produce un token ya caducado para
    testear el 401 de expiración.
    """
    from backend.app.config import get_settings

    now = dt.datetime.now(dt.timezone.utc)
    claims = {
        "sub": str(sub),
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + (expires_delta if expires_delta is not None else dt.timedelta(hours=1)),
    }
    token = jwt.encode(claims, get_settings().supabase_jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Headers Bearer propios de un usuario de prueba, para los endpoints protegidos."""
    return make_auth_headers()
