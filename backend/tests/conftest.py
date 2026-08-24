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

import os

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
