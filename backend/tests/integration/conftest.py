"""Tests de integración de repositories/ contra Postgres REAL.

La auditoría crítica señalaba que ninguna query SQL estaba cubierta por CI: aquí se ejercitan
`insert_many`, `list_recent`, `last_results`, `champion_performance`, `lp_trend` y `nemesis`
contra un Postgres de verdad con el esquema de `backend/migrations/*.sql` ya aplicado.

Requisitos:
  * `TEST_DATABASE_URL` en el entorno (el workflow del CI la exporta y aplica las migraciones
    antes de pytest).
  * Si la DB no lleva TLS (postgres efímero local/CI), exportar también `DB_SSLMODE=disable`;
    los repos abren el pool vía config.Settings, que por defecto exige TLS (Supabase).

Sin `TEST_DATABASE_URL` toda la carpeta se ignora: en local sin Postgres, la suite hermética
(27 tests) sigue siendo el comportamiento por defecto y no hay intentos de conexión colgados.
"""

from __future__ import annotations

import os
import pathlib

if not os.environ.get("TEST_DATABASE_URL"):
    collect_ignore = [p.name for p in pathlib.Path(__file__).parent.glob("test_*.py")]
