"""Backup real de la base de datos (Supabase/PostgreSQL) con pg_dump.

Sustituye al backup_db.py del monolito, que copiaba el SQLite huérfano de data/ y no
protegía nada actual. Este vuelca schema + datos completos a backups/.

Requisito: el binario `pg_dump` en el PATH. En Windows viene con cualquier instalación
de PostgreSQL (o `winget install PostgreSQL.PostgreSQL`); en el devcontainer lo instala
el postCreateCommand.

Uso (desde la raíz del repo):
    python -m backend.scripts.backup_supabase
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"


def main() -> int:
    pg_dump = shutil.which("pg_dump")
    if pg_dump is None:
        print(
            "ERROR: `pg_dump` no está en el PATH.\n"
            "  Windows : instala PostgreSQL Client Tools (winget install PostgreSQL.PostgreSQL)\n"
            "            y añade su carpeta /bin al PATH.\n"
            "  Devcontainer: ya lo instala el postCreateCommand; reconstruye el contenedor."
        )
        return 1

    # Reutiliza la configuración validada del backend (.env). Si falta alguna variable,
    # get_settings() falla aquí con un mensaje claro, antes de tocar nada.
    from backend.app.config import get_settings

    settings = get_settings()
    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"backup_{timestamp}.sql"

    cmd = [
        pg_dump,
        "--host", settings.db_host,
        "--port", str(settings.db_port),
        "--username", settings.db_user,
        "--dbname", settings.db_name,
        # Sin owner/privileges: al restaurar en otro proyecto Supabase los roles no existen.
        "--no-owner",
        "--no-privileges",
        "--encoding", "UTF8",
        "--file", str(dest),
    ]

    # PGPASSWORD evita prompt interactivo; PGSSLMODE=require porque Supabase siempre va por TLS.
    env = os.environ | {"PGPASSWORD": settings.db_password, "PGSSLMODE": "require"}

    print(f"Volcando {settings.db_user}@{settings.db_host}/{settings.db_name} -> {dest.name} ...")
    result = subprocess.run(cmd, env=env)  # noqa: S603
    if result.returncode != 0:
        print(f"ERROR: pg_dump terminó con código {result.returncode}. Backup NO válido.")
        if dest.exists():
            dest.unlink()
        return result.returncode

    size_kb = dest.stat().st_size / 1024
    print(f"✅ Backup completo (schema + datos): {dest} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
