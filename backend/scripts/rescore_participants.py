"""Re-puntúa los participantes ya sincronizados con la fórmula ACTUAL del rating.

Las partidas guardadas antes de `_ROLE_PROFILES` llevan ratings de la fórmula antigua (o del
fallback `computeRating()` del frontend): mezclar dos matemáticas en los rankings corrompe
cualquier comparación. Este script reescribe SOLO la columna `participants` de cada fila de
`matches`, recalculando `rating` con la función vigente y estampando `rating_version`. Los
campos subjetivos (lp_change, tilt_level, impact_rating, notes, vod_review) no se tocan:
nunca salen del SELECT.

Idempotente: ejecutarlo dos veces produce los mismos valores (segunda pasada, 0 cambios).

Uso (desde la raíz del repo):
    python -m backend.scripts.rescore_participants
"""

from __future__ import annotations

import json
import sys
from typing import Any

SELECT_SQL = (
    "SELECT game_id, game_duration_minutes, cs_total, cs_min, participants "
    "FROM matches ORDER BY date ASC"
)
UPDATE_SQL = "UPDATE matches SET participants = %s::jsonb WHERE game_id = %s"


def _duration_minutes(row: dict[str, Any]) -> float | None:
    """Duración en minutos que necesita la fórmula.

    Las filas legacy migradas del SQLite pueden no traer game_duration_minutes; se deriva de
    cs_total / cs_min (el monolito guardaba ambos). Si tampoco hay, no hay rating posible.
    """
    if row["game_duration_minutes"]:
        return float(row["game_duration_minutes"])
    cs_min = row["cs_min"]
    if cs_min and float(cs_min) > 0:
        return round(float(row["cs_total"]) / float(cs_min), 2)
    return None


def main() -> int:
    # Imports diferidos como en los demás scripts: el fallo de .env o de driver sale aquí,
    # con mensaje claro, sin stacktrace críptico.
    from backend.app.config import get_settings
    from backend.app.schemas import RATING_VERSION
    from backend.app.services.riot import RiotService

    settings = get_settings()
    try:
        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(settings.dsn, connect_timeout=15)
    except Exception as exc:
        print(f"[ERROR] No se pudo conectar a Supabase: {type(exc).__name__}: {exc}")
        return 1

    updated_matches = 0
    updated_players = 0
    changed_ratings = 0
    skipped = 0

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(SELECT_SQL)
            rows = cur.fetchall()

            total = len(rows)
            print(
                f"{total} partidas encontradas. Recalculando ratings con la fórmula v{RATING_VERSION}...\n"
            )

            for i, row in enumerate(rows, start=1):
                gid = row["game_id"]
                participants: list[dict[str, Any]] | None = row["participants"]

                if not participants:
                    skipped += 1
                    print(f"[{i}/{total}] {gid}: sin participantes en JSONB (fila legacy), omitida")
                    continue

                duration = _duration_minutes(row)
                if duration is None:
                    skipped += 1
                    print(f"[{i}/{total}] {gid}: sin duración conocida, omitida")
                    continue

                for p in participants:
                    old_rating = p.get("rating")
                    p["rating"] = RiotService.calculate_participant_rating(p, duration)
                    p["rating_version"] = RATING_VERSION
                    updated_players += 1
                    if old_rating != p["rating"]:
                        changed_ratings += 1

                # UPDATE quirúrgico: sólo la columna participants; lo subjetivo queda intacto.
                cur.execute(UPDATE_SQL, (json.dumps(participants), gid))
                conn.commit()  # commit incremental: un Ctrl-C conserva lo ya procesado
                updated_matches += 1
                print(f"[{i}/{total}] {gid}: {len(participants)} participantes re-puntuados")

    except KeyboardInterrupt:
        conn.rollback()
        print("\n[INTERRUMPIDO] Se conservan las partidas ya confirmadas.")
        return 130
    except Exception as exc:
        conn.rollback()
        print(f"\n[ERROR] Fallo el re-puntuado, rollback aplicado: {exc}")
        return 1
    finally:
        conn.close()

    print(
        f"\n✅ Re-puntuado completo: {updated_matches} partidas, {updated_players} participantes "
        f"(ratings cambiados: {changed_ratings}, omitidas: {skipped})."
    )
    if skipped:
        print("   Revisa las omitidas arriba: o son filas legacy sin JSONB o sin duración.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
