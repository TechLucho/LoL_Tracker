"""Resolución dinámica del parche y metadatos de Data Dragon.

PROBLEMA: `current_patch = "14.24.1"` estaba hardcodeado en `app.py:530` para las URLs de
iconos de Data Dragon. Los campeones nuevos daban 404 porque el parche era de finales de 2024.

SOLUCIÓN: consultar `https://ddragon.leagueoflegends.com/api/versions.json` (devuelve un array
de strings, el primero es el más reciente) y cachear el resultado. El endpoint `/api/datadragon/version`
expone el parche actual para que el frontend no lo duplique.

Hub de metadatos (Sprint 2): además de la versión, se descargan campeones, objetos y hechizos
del parche vigente y se sirven ya recortados (id -> nombre, descripción limpia, URL de imagen).
El JSON crudo de Data Dragon ronda varios MB; transformarlo en el backend evita que cada cliente
lo descargue y parseé entero. Cacheados con el mismo TTL de 1h; si la descarga falla se sirve la
copia expirada mientras exista.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

log = logging.getLogger(__name__)

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
CDN_BASE = "https://ddragon.leagueoflegends.com/cdn"
CACHE_TTL_SECONDS = 3600  # 1 hora

_cache: dict[str, str | float] = {"patch": "", "fetched_at": 0.0}

# kind -> (fetched_at, payload). Un solo lock: tres descargas concurrentes del mismo JSON son
# un desperdicio, no una carrera peligrosa.
_metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_metadata_lock = asyncio.Lock()

# Las descripciones de Data Dragon traen HTML (<mainText>, <stats>, <br>...): se aplana a texto.
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(raw: str) -> str:
    return " ".join(_TAG_RE.sub(" ", raw or "").split())


async def get_current_patch() -> str:
    """Devuelve el parche más reciente de Data Dragon, con caché de 1h."""
    now = time.time()
    if _cache["patch"] and (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS:
        return _cache["patch"]  # type: ignore[return-value]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(VERSIONS_URL)
            resp.raise_for_status()
            versions: list[str] = resp.json()
            if not versions:
                raise ValueError("Data Dragon devolvió un array vacío")
            patch = versions[0]
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo obtener versión de Data Dragon: %s", exc)
        if _cache["patch"]:
            log.info("Usando caché expirado: %s", _cache["patch"])
            return _cache["patch"]  # type: ignore[return-value]
        raise RuntimeError("No hay parche de Data Dragon disponible") from exc

    _cache["patch"] = patch
    _cache["fetched_at"] = now
    log.info("Data Dragon parche actual: %s", patch)
    return patch


def dragon_url(patch: str, path: str) -> str:
    """Construye una URL completa de Data Dragon.

    Ejemplo:
        dragon_url("14.24.1", "img/champion/Aatrox.png")
        → "https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/Aatrox.png"
    """
    return f"https://ddragon.leagueoflegends.com/cdn/{patch}/{path}"


async def _get_index(
    kind: str,
    file_name: str,
    transform: Callable[[dict[str, Any], str], dict[str, Any]],
) -> dict[str, Any]:
    """Descarga (con caché de 1h) un JSON de datos del parche vigente y lo transforma."""
    cached = _metadata_cache.get(kind)
    if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    async with _metadata_lock:
        cached = _metadata_cache.get(kind)  # doble check: otro request pudo rellenarla ya
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        patch = await get_current_patch()
        url = f"{CDN_BASE}/{patch}/data/en_US/{file_name}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.json()

        data = transform(raw, patch)
        _metadata_cache[kind] = (time.time(), data)
        # Todos los payloads son {patch, <colección>}: la colección es el segundo valor.
        entries = next(iter(data.values()))
        log.info("Metadatos '%s' del parche %s: %d entradas", kind, patch, len(entries))
        return data


def _transform_champions(raw: dict[str, Any], patch: str) -> dict[str, Any]:
    champions = {
        champ["id"]: {
            "id": champ["id"],
            "name": champ.get("name", ""),
            "title": champ.get("title", ""),
            "description": _clean_html(champ.get("blurb", "")),
            "image": dragon_url(patch, f"img/champion/{champ['image']['full']}"),
        }
        for champ in raw["data"].values()
    }
    return {"patch": patch, "champions": champions}


def _transform_items(raw: dict[str, Any], patch: str) -> dict[str, Any]:
    items = {}
    for item_id, item in raw["data"].items():
        items[item_id] = {
            # Los ids llegan como claves string ("3078"); el frontend indexa igual.
            "id": int(item_id),
            "name": item.get("name", ""),
            "description": _clean_html(item.get("description", "")),
            "plaintext": item.get("plaintext", ""),
            "image": dragon_url(patch, f"img/item/{item['image']['full']}"),
        }
    return {"patch": patch, "items": items}


def _transform_spells(raw: dict[str, Any], patch: str) -> dict[str, Any]:
    spells = {}
    for spell in raw["data"].values():
        spell_key = int(spell["key"])  # "SummonerFlash" tiene key numérica "4"
        spells[str(spell_key)] = {
            "id": spell_key,
            "name": spell.get("name", ""),
            "description": _clean_html(spell.get("description", "")),
            "image": dragon_url(patch, f"img/spell/{spell['image']['full']}"),
        }
    return {"patch": patch, "spells": spells}


async def get_champions() -> dict[str, Any]:
    """Campeones del parche vigente, clave = id de Data Dragon ('LeeSin')."""
    return await _get_index("champions", "champion.json", _transform_champions)


async def get_items() -> dict[str, Any]:
    """Objetos del parche vigente, clave = id numérico ('3078')."""
    return await _get_index("items", "item.json", _transform_items)


async def get_spells() -> dict[str, Any]:
    """Hechizos de invocador, clave = id numérico de partida ('4' = Flash)."""
    return await _get_index("spells", "summoner.json", _transform_spells)
