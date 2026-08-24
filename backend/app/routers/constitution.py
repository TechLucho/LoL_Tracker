"""La Constitución — motor de disciplina anti-tilt.

Cruza la configuración del usuario (champion pool, max deaths, target CS/min) con las
últimas partidas para generar un veredicto: SAFE / WARNING / STOP.
"""

from __future__ import annotations

import statistics
from typing import Any

from fastapi import APIRouter

from backend.app.repositories import matches as matches_repo
from backend.app.repositories import settings as settings_repo

router = APIRouter(prefix="/api/constitution", tags=["constitution"])

# ── Schema de respuesta ─────────────────────────────────────────────────────

def _rule(name: str, passed: bool, message: str, detail: str = "", severity: str = "fail") -> dict[str, Any]:
    return {
        "rule": name,
        "status": "PASS" if passed else "FAIL",
        "severity": severity,  # "pass" | "fail" | "warning"
        "message": message,
        "detail": detail,
    }


# ── Endpoint ────────────────────────────────────────────────────────────────

@router.get("/status")
async def constitution_status() -> dict[str, Any]:
    cfg = await settings_repo.get()
    champion_pool: list[str] = cfg.get("champion_pool") or []
    max_deaths: float = float(cfg.get("max_deaths") or 8)
    target_cs_min: float = float(cfg.get("target_cs_min") or 7.0)

    # Últimas 5 partidas válidas (máximo; puede haber menos): sólo Solo/Duo de 5+ minutos,
    # para que un remake no dispare el STOP ni contamine la media de muertes. Ver
    # matches_repo.last_results().
    recent = await matches_repo.last_results(limit=5)
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
    pool_lower = {c.lower() for c in champion_pool}
    off_pool = [m for m in recent if m.get("champion", "").lower() not in pool_lower]

    if off_pool:
        champs = ", ".join(sorted({m["champion"] for m in off_pool}))
        rules.append(_rule(
            "pool_fidelity",
            passed=False,
            message=f"Estás jugando campeones fuera de tu pool: {champs}.",
            detail=f"{len(off_pool)} de {len(recent)} partidas fuera de pool.",
        ))
    elif champion_pool:
        rules.append(_rule(
            "pool_fidelity",
            passed=True,
            message="Fidelidad al champion pool: perfecta.",
            detail=f"Todas las partidas con campeones del pool ({', '.join(champion_pool)}).",
        ))
    else:
        rules.append(_rule(
            "pool_fidelity",
            passed=True,
            message="Sin champion pool configurado — regla deshabilitada.",
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
            detail=f"Límite: {max_deaths} · Tendencia: {'▲' if len(deaths_list) >= 2 and deaths_list[0] > deaths_list[-1] else '▼' if len(deaths_list) >= 2 and deaths_list[0] < deaths_list[-1] else '→'}",
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
            detail=f"Objetivo: {target_cs_min} · Tendencia: {'▲' if len(cs_list) >= 2 and cs_list[0] > cs_list[-1] else '▼' if len(cs_list) >= 2 and cs_list[0] < cs_list[-1] else '→'}",
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

    # Stats resumen
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
