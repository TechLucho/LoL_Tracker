"""Migración del SQLite legacy (data/lol_tracker.db) a Supabase/PostgreSQL.

Tres modos independientes, pensados para ejecutarse en este orden:

    export   Vuelca las partidas del SQLite a data/legacy_matches.json (NO necesita credenciales).
             Saca el historial de un archivo gitignoreado a uno versionable.
    import   Inserta ese JSON en Supabase con ON CONFLICT DO NOTHING (idempotente, re-ejecutable).
    verify   Compara game_ids entre el JSON y Supabase, y dice si ya es seguro borrar el .db.

Uso (desde la raíz del repo):
    python -m backend.scripts.migrate_sqlite export
    python -m backend.scripts.migrate_sqlite import
    python -m backend.scripts.migrate_sqlite verify
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SQLITE_PATH = ROOT / "data" / "lol_tracker.db"
EXPORT_PATH = ROOT / "data" / "legacy_matches.json"

# Zona en la que se asume que se registraron las partidas legacy (el monolito guardaba la hora
# local del host, sin zona). Sobrescribible con --tz.
LEGACY_TZ = "Europe/Madrid"

# Orden canónico de columnas. El SQLite legacy y la tabla de Postgres comparten
# nombres; lo que cambia son los tipos (ver _coerce).
COLUMNS = [
    "game_id", "date", "champion", "role",
    "kills", "deaths", "assists",
    "cs_total", "cs_min", "control_wards", "win",
    "enemy_champion", "game_duration_minutes",
    "lp_change", "tilt_level", "impact_rating", "notes", "vod_review",
]

# Columnas que en SQLite son INTEGER 0/1 y en Postgres son BOOLEAN.
BOOL_COLUMNS = {"win", "vod_review"}


def _coerce(row: sqlite3.Row) -> dict[str, Any]:
    """Normaliza una fila de SQLite a tipos que Postgres acepta directamente."""
    out: dict[str, Any] = {}
    for col in COLUMNS:
        value = row[col]
        if col in BOOL_COLUMNS:
            out[col] = None if value is None else bool(value)
        elif col == "date" and value is not None:
            # SQLite guarda 'YYYY-MM-DD HH:MM:SS' como TEXT -> validamos y dejamos ISO.
            out[col] = datetime.fromisoformat(str(value)).isoformat(sep=" ")
        else:
            out[col] = value
    return out


def cmd_export() -> int:
    if not SQLITE_PATH.exists():
        print(f"[ERROR] No existe {SQLITE_PATH}")
        return 1

    conn = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM matches ORDER BY date ASC"
        ).fetchall()
    finally:
        conn.close()

    matches = [_coerce(r) for r in rows]
    payload = {
        "source": "data/lol_tracker.db (SQLite legacy, pre-migracion a Supabase)",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(matches),
        "columns": COLUMNS,
        "matches": matches,
    }
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"[OK] {len(matches)} partidas exportadas -> {EXPORT_PATH.relative_to(ROOT)}")
    if matches:
        print(f"     rango: {matches[0]['date']}  ->  {matches[-1]['date']}")
        sin_lp = sum(1 for m in matches if m["lp_change"] is None)
        sin_notas = sum(1 for m in matches if not m["notes"])
        print(f"     campos subjetivos vacios: {sin_lp} sin lp_change, {sin_notas} sin notas")
        print("\n     Partidas:")
        for m in matches:
            print(
                f"       {m['date']}  {m['champion']:<12} vs {str(m['enemy_champion']):<12}"
                f"  {m['kills']}/{m['deaths']}/{m['assists']}  {'W' if m['win'] else 'L'}"
            )
    return 0


def _load_export() -> list[dict[str, Any]]:
    if not EXPORT_PATH.exists():
        print(f"[ERROR] No existe {EXPORT_PATH}. Ejecuta primero el modo 'export'.")
        sys.exit(1)
    return json.loads(EXPORT_PATH.read_text(encoding="utf-8"))["matches"]


def _connect():
    """Conexión a Supabase. Import diferido para que 'export' no requiera driver."""
    from backend.app.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    try:
        import psycopg  # noqa: PLC0415

        return psycopg.connect(settings.dsn, connect_timeout=15)
    except ModuleNotFoundError:
        import psycopg2  # noqa: PLC0415

        return psycopg2.connect(settings.dsn, connect_timeout=15)


def cmd_import(legacy_tz: str = LEGACY_TZ) -> int:
    matches = _load_export()

    # Las fechas del SQLite son naive: son la hora LOCAL de la máquina que sincronizó. La tabla
    # nueva usa TIMESTAMPTZ (ver migrations/002), así que hay que declarar en qué zona estaban.
    # Sin esto, Postgres las interpretaría en la zona de la sesión y el heatmap se desplazaría.
    zone = ZoneInfo(legacy_tz)
    for m in matches:
        if m["date"]:
            m["date"] = datetime.fromisoformat(m["date"]).replace(tzinfo=zone)

    placeholders = ", ".join(["%s"] * len(COLUMNS))
    query = (
        f"INSERT INTO matches ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
        "ON CONFLICT (game_id) DO NOTHING"
    )

    try:
        conn = _connect()
    except Exception as exc:  # credenciales aun sin rotar
        print(f"[ERROR] No se pudo conectar a Supabase: {type(exc).__name__}: {exc}")
        print("        Rota DB_PASSWORD en Supabase y actualiza .env antes de importar.")
        return 1

    inserted = 0
    try:
        with conn.cursor() as cur:
            for m in matches:
                cur.execute(query, [m[c] for c in COLUMNS])
                inserted += cur.rowcount
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"[ERROR] Fallo la importacion, rollback aplicado: {exc}")
        return 1
    finally:
        conn.close()

    skipped = len(matches) - inserted
    print(f"[OK] {inserted} insertadas, {skipped} ya existian (total en JSON: {len(matches)})")
    return 0


def cmd_verify() -> int:
    matches = _load_export()
    expected = {m["game_id"] for m in matches}

    try:
        conn = _connect()
    except Exception as exc:
        print(f"[ERROR] No se pudo conectar a Supabase: {type(exc).__name__}: {exc}")
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT game_id FROM matches")
            present = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()

    missing = expected - present
    print(f"JSON legacy : {len(expected)} partidas")
    print(f"Supabase    : {len(present)} partidas totales")
    print(f"Legacy en Supabase: {len(expected & present)}/{len(expected)}")

    if missing:
        print(f"\n[PENDIENTE] Faltan {len(missing)} en Supabase:")
        for gid in sorted(missing):
            print(f"   {gid}")
        print("\n   NO borres data/lol_tracker.db todavia.")
        return 1

    print("\n[OK] Todo el historial legacy esta en Supabase.")
    print("     data/lol_tracker.db ya es seguro de archivar.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["export", "import", "verify"])
    parser.add_argument(
        "--tz",
        default=LEGACY_TZ,
        help=f"Zona horaria en la que se registraron las partidas legacy (def: {LEGACY_TZ})",
    )
    args = parser.parse_args()

    if args.mode == "export":
        return cmd_export()
    if args.mode == "import":
        return cmd_import(args.tz)
    return cmd_verify()


if __name__ == "__main__":
    sys.exit(main())
