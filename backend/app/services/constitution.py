"""La Constitución: la regla anti-tilt del proyecto.

Estaba enterrada en el sidebar de Streamlit, mezclada con código de presentación. Aquí es lógica
de dominio pura y testeable, sin dependencias de UI.

Reglas (bloques de 3 partidas):
  * 2+ derrotas consecutivas -> STOP obligatorio.
  * 3 victorias de 3         -> ON FIRE, seguir jugando.
  * cualquier otra cosa      -> NEUTRAL.
"""

from __future__ import annotations

from typing import Any

BLOCK_SIZE = 3
STOP_LOSS_THRESHOLD = 2


def evaluate(recent: list[dict[str, Any]]) -> dict[str, Any]:
    """`recent` son las últimas partidas, más reciente primero."""
    if not recent:
        return {
            "state": "NO_DATA",
            "message": "Sin partidas registradas. Sincroniza para empezar.",
            "loss_streak": 0,
            "last_results": [],
        }

    results = [bool(m["win"]) for m in recent[:BLOCK_SIZE]]

    loss_streak = 0
    for won in results:
        if won:
            break
        loss_streak += 1

    if loss_streak >= STOP_LOSS_THRESHOLD:
        return {
            "state": "STOP",
            "message": (
                f"⛔ STOP OBLIGATORIO. Llevas {loss_streak} derrotas seguidas. "
                "Cierra el juego 1 hora."
            ),
            "loss_streak": loss_streak,
            "last_results": results,
        }

    if len(results) == BLOCK_SIZE and all(results):
        return {
            "state": "ON_FIRE",
            "message": "🔥 ON FIRE. 3/3 victorias. Sigue jugando hasta perder.",
            "loss_streak": 0,
            "last_results": results,
        }

    racha = " ".join("✅" if won else "❌" for won in results)
    return {
        "state": "NEUTRAL",
        "message": f"Racha: {racha}. Recuerda: bloques de 3 partidas.",
        "loss_streak": loss_streak,
        "last_results": results,
    }


def is_off_pool(champion: str, champion_pool: list[str]) -> bool:
    """True si el campeón jugado está fuera del pool declarado (comparación case-insensitive).

    Se normaliza ANTES de comprobar si el pool está vacío, no después: el pool llega de un campo
    de texto separado por comas, así que un campo vacío produce `[""]` y uno mal editado puede dar
    `["Jax", ""]`. Comprobar sólo `if not champion_pool` dejaría pasar `[""]` como un pool válido
    y vacío, y entonces *todo* campeón se marcaría como fuera de pool: una falsa alarma constante.
    """
    normalized = {c.strip().lower() for c in champion_pool if c.strip()}
    if not normalized:
        return False
    return champion.strip().lower() not in normalized
