"""Líneas base (baselines) por rol para comparar contra la ladder global.

La UI de Full Stats pinta el valor real de cada métrica frente a lo "esperable" para el rol
(la línea, la jungla o el soporte "normales"), con verde/flecha arriba cuando lo superas.

Los targets de CS/min, DPM y KP% espejan los del rating (`_ROLE_PROFILES` en riot.py) para
que las dos métricas nunca se contradigan. La visión no tiene baseline en el rating para los
carriles (sólo jungla y soporte lo puntúan), así que aquí se declara para los cinco roles:
es la métrica que más pesa en soporte y la vista la compara por partida.

Unidades comparables con lo que guarda el sync por participante:
  * `cs_per_min`, `dpm`, `kill_participation` (ratio 0-1, igual que el JSONB);
  * `vision_per_min`: la puntuación de visión es POR PARTIDA, así que el esperado total se
    calcula multiplicando por la duración real (`expected_stats_for`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoleBaseline:
    """Estadísticas 'normales' de un rol, en las mismas unidades que el participante."""

    cs_per_min: float
    dpm: float
    kill_participation: float  # ratio 0-1
    vision_per_min: float


ROLE_BASELINES: dict[str, RoleBaseline] = {
    "TOP": RoleBaseline(cs_per_min=7.5, dpm=600, kill_participation=0.55, vision_per_min=0.3),
    "MIDDLE": RoleBaseline(cs_per_min=7.5, dpm=650, kill_participation=0.60, vision_per_min=0.3),
    "BOTTOM": RoleBaseline(cs_per_min=7.5, dpm=600, kill_participation=0.65, vision_per_min=0.3),
    "JUNGLE": RoleBaseline(cs_per_min=5.75, dpm=500, kill_participation=0.70, vision_per_min=0.5),
    "UTILITY": RoleBaseline(cs_per_min=1.25, dpm=250, kill_participation=0.70, vision_per_min=1.0),
}

# ARAM, remakes, roles sin asignar ("Unknown"): perfil neutro.
DEFAULT_BASELINE = RoleBaseline(cs_per_min=7.0, dpm=550, kill_participation=0.50, vision_per_min=0.3)


def baseline_for(role: str | None) -> RoleBaseline:
    """Línea base de un rol; perfil neutro si el rol es desconocido/vacío."""
    return ROLE_BASELINES.get((role or "").upper(), DEFAULT_BASELINE)


def expected_stats_for(role: str | None, duration_minutes: float | None) -> dict[str, float]:
    """Lo 'esperado' de un rol en una partida concreta, en unidades del participante.

    KP% como ratio 0-1 (mismo formato que `kill_participation` del JSONB). La visión esperada
    es un total proporcional a la duración de la partida (`vision_per_min × duración`).
    """
    base = baseline_for(role)
    duration = max(float(duration_minutes or 0), 1.0)
    return {
        "cs_per_min": base.cs_per_min,
        "dpm": base.dpm,
        "kill_participation": base.kill_participation,
        "vision_score": round(base.vision_per_min * duration, 1),
    }


def enrich_match_row(row: dict) -> dict:
    """Adjunta `expected_stats` a cada participante de una fila de `matches`.

    Se calcula en lectura (nunca se persiste: no hay migración y el dato no envejece). Las
    filas legacy sin `participants` pasan intactas, y los roles desconocidos reciben el perfil
    neutro en vez de romper la serialización.
    """
    participants = row.get("participants")
    if not participants:
        return row
    duration = row.get("game_duration_minutes")
    enriched = [
        {**p, "expected_stats": expected_stats_for(p.get("team_position"), duration)}
        for p in participants
    ]
    return {**row, "participants": enriched}