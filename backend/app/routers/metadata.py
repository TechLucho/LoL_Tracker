"""Hub de metadatos de League of Legends (Data Dragon), cacheado en el backend.

- GET /api/metadata/champions → {patch, champions: {id_dd: {name, title, image, ...}}}
- GET /api/metadata/items     → {patch, items: {"3078": {name, description, image, ...}}}
- GET /api/metadata/spells    → {patch, spells: {"4": {name, description, image}}}

Antes cada vista del frontend construía URLs con un parche hardcodeado y mantenía a mano un
mapa de excepciones de nombres de campeón. Ahora el backend sirve los diccionarios ya limpios
(id -> nombre, descripción sin HTML, URL absoluta) y cacheados 1h; el frontend sólo consume.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas import ChampionsIndex, ItemsIndex, SpellsIndex
from backend.app.services import datadragon

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get("/champions", response_model=ChampionsIndex)
async def champions() -> dict[str, object]:
    """Campeones del parche vigente. Clave = id de Data Dragon ('LeeSin'); `name` es el nombre
    visible que la DB guarda en matches.champion/participants.champion_name."""
    try:
        return await datadragon.get_champions()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No se pudieron descargar los campeones de Data Dragon",
        ) from exc


@router.get("/items", response_model=ItemsIndex)
async def items() -> dict[str, object]:
    """Objetos del parche vigente. Clave = id numérico de Riot ('3078')."""
    try:
        return await datadragon.get_items()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No se pudieron descargar los objetos de Data Dragon",
        ) from exc


@router.get("/spells", response_model=SpellsIndex)
async def spells() -> dict[str, object]:
    """Hechizos de invocador. Clave = id numérico de partida ('4' = Flash)."""
    try:
        return await datadragon.get_spells()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No se pudieron descargar los hechizos de Data Dragon",
        ) from exc
