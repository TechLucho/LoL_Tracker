"""La Constitución: el motor anti-tilt del proyecto, lógica de dominio pura y testeable.

Un solo motor (decisión 2026-09-11): el antiguo `/api/stats/constitution` y su `evaluate()`
de bloques de 3 partidas se eliminaron por duplicados. Este servicio alimenta el único
endpoint activo (`/api/constitution/status`) y no hace I/O: el router le pasa la
configuración y la ventana de partidas (`matches_repo.last_results`).

Reglas evaluadas sobre las `recent` partidas válidas (más reciente primero):
  * Racha de derrotas: 2+ consecutivas -> dejar de jugar.
  * Fidelidad al champion pool (normalizado; pool vacío = regla deshabilitada).
  * Muerte media por partida contra el límite declarado.
  * Farmeo: CS/min medio contra el objetivo.
"""

from __future__ import annotations

import statistics
from typing import Any

# Ventana de partidas que decide el veredicto (la que expone el endpoint).
RECENT_WINDOW = 5


def _rule(name: str, passed: bool, message: str, detail: str = "", severity: str | None = None) -> dict[str, Any]:
    return {
        "rule": name,
        "status": "PASS" if passed else "FAIL",
        "severity": severity or ("pass" if passed else "fail"),  # "pass" | "fail" | "warning"
        "message": message,
        "detail": detail,
    }


def _trend(values: list[float]) -> str:
    if len(values) >= 2:
        if values[0] > values[-1]:
            return "▲"
        if values[0] < values[-1]:
            return "▼"
    return "→"


def evaluate_rules(
    *,
    champion_pool: list[str],
    max_deaths: float,
    target_cs_min: float,
    recent: list[dict[str, Any]],
) -> dict[str, Any]:
    """Motor puro de La Constitución. `recent` = últimas N partidas, más reciente primero."""
    if not recent:
        return {
            "global_status": "NO DATA",
            "message": "No hay partidas registradas.",
            "rules": [],
            "stats": {},
        }

    rules: list[dict[str, Any]] = []

    # ── Regla 1: Racha de derrotas ──────────────────────────────────────────
    consecutive_losses = 0
    for m in recent:
        if not m.get("win"):
            consecutive_losses += 1
        else:
            break

    if consecutive_losses >= 2:
        rules.append(_rule(
            "loss_streak",
            passed=False,
            message=f"Has perdido {consecutive_losses} seguidas. PARA DE JUGAR.",
            detail=f"Últimas {consecutive_losses} partidas: todas derrotas.",
        ))
    else:
        rules.append(_rule(
            "loss_streak",
            passed=True,
            message="Racha de derrotas controlada.",
            detail=f"{consecutive_losses} derrota(s) consecutiva(s).",
        ))

    # ── Regla 2: Fidelidad al champion pool ─────────────────────────────────
    # Normalización anti falsos positivos (heredada del antiguo is_off_pool): el pool llega de
    # un campo de texto separado por comas (frontend) o de una lista (API), así que un campo
    # vacío producía `[""]` y *todo* campeón habría salido como fuera de pool.
    pool_normalized = {c.strip().lower() for c in champion_pool if c.strip()}

    if not pool_normalized:
        rules.append(_rule(
            "pool_fidelity",
            passed=True,
            message="Sin champion pool configurado — regla deshabilitada.",
        ))
    else:
        off_pool = [m for m in recent if m.get("champion", "").strip().lower() not in pool_normalized]
        if off_pool:
            champs = ", ".join(sorted({m["champion"] for m in off_pool}))
            rules.append(_rule(
                "pool_fidelity",
                passed=False,
                message=f"Estás jugando campeones fuera de tu pool: {champs}.",
                detail=f"{len(off_pool)} de {len(recent)} partidas fuera de pool.",
            ))
        else:
            rules.append(_rule(
                "pool_fidelity",
                passed=True,
                message="Fidelidad al champion pool: perfecta.",
                detail=f"Todas las partidas con campeones del pool ({', '.join(champion_pool)}).",
            ))

    # ── Regla 3: Límite de muertes ──────────────────────────────────────────
    deaths_list = [m.get("deaths", 0) for m in recent]
    avg_deaths = statistics.mean(deaths_list) if deaths_list else 0

    if avg_deaths > max_deaths:
        rules.append(_rule(
            "death_limit",
            passed=False,
            message=f"Muerte media ({avg_deaths:.1f}) supera tu límite ({max_deaths}).",
            detail=f"Últimas {len(recent)} partidas: {deaths_list}.",
        ))
    elif avg_deaths > max_deaths * 0.8:
        rules.append(_rule(
            "death_limit",
            passed=True,
            message=f"Muerte media ({avg_deaths:.1f}) cerca del límite ({max_deaths}).",
            detail=f"Cuidado, estás al {avg_deaths / max_deaths * 100:.0f}% del límite.",
            severity="warning",
        ))
    else:
        rules.append(_rule(
            "death_limit",
            passed=True,
            message=f"Muerte media ({avg_deaths:.1f}) dentro del rango.",
            detail=f"Límite: {max_deaths} · Tendencia: {_trend(deaths_list)}",
        ))

    # ── Regla 4: Farmeo ─────────────────────────────────────────────────────
    cs_list = [m.get("cs_min", 0) for m in recent]
    avg_cs = statistics.mean(cs_list) if cs_list else 0

    if avg_cs < target_cs_min:
        rules.append(_rule(
            "cs_farming",
            passed=False,
            message=f"CS/min ({avg_cs:.1f}) por debajo del objetivo ({target_cs_min}).",
            detail=f"Últimas {len(recent)} partidas: {[round(c, 1) for c in cs_list]}.",
            severity="warning",
        ))
    else:
        rules.append(_rule(
            "cs_farming",
            passed=True,
            message=f"CS/min ({avg_cs:.1f}) en rango objetivo.",
            detail=f"Objetivo: {target_cs_min} · Tendencia: {_trend(cs_list)}",
        ))

    # ── Global status ───────────────────────────────────────────────────────
    has_hard_fail = any(r["status"] == "FAIL" for r in rules)
    has_warning = any(r["severity"] == "warning" or r["status"] == "FAIL" for r in rules)

    if has_hard_fail:
        global_status = "STOP PLAYING (TILTED)"
        global_message = "La Constitución ha detectado violaciones. Tómate un descanso."
    elif has_warning:
        global_status = "WARNING"
        global_message = "Algunas reglas están al límite. Juega con cuidado."
    else:
        global_status = "SAFE TO PLAY"
        global_message = "Todo en orden. A por la victoria."

    wins = sum(1 for m in recent if m.get("win"))
    stats_summary = {
        "games_analyzed": len(recent),
        "wins": wins,
        "losses": len(recent) - wins,
        "avg_deaths": round(avg_deaths, 1),
        "avg_cs_min": round(avg_cs, 1),
        "consecutive_losses": consecutive_losses,
    }

    return {
        "global_status": global_status,
        "message": global_message,
        "rules": rules,
        "stats": stats_summary,
    }