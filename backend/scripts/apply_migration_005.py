"""Aplica la migración 005_lp_snapshots.sql contra Supabase (uso one-off)."""

from pathlib import Path

import psycopg

from backend.app.config import get_settings

ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = ROOT / "backend" / "migrations" / "005_lp_snapshots.sql"


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    settings = get_settings()
    with psycopg.connect(settings.dsn) as conn:
        conn.execute(sql)
        conn.commit()
        row = conn.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'lp_snapshots'
            """
        ).fetchone()
    print("Migración 005 aplicada. Tabla lp_snapshots existe:", bool(row and row[0]))


if __name__ == "__main__":
    main()
