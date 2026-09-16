"""Broadcast Realtime de Supabase hacia el canal `room:{code}` (Sprint 3).

El estado vivo cambia en el backend (árbitro, Regla 1); el backend lo difunde a los
frontends suscritos usando el endpoint **REST de Broadcast** de Supabase Realtime:

    POST /realtime/v1/api/broadcast
    { "messages": [{ "topic": "room:CODE", "event": "state", "payload": {…} }] }

Prefiero HTTP a un cliente websocket (supabase-py) porque:
  * cero dependencias nuevas (httpx ya está en requirements.txt);
  * el backend no mantiene una conexión de websocket abierta ni hilos de reconnect;
  * en el evento loop async de FastAPI/Windows es totalmente fiable.

Configuración: `SUPABASE_URL` y `SUPABASE_ANON_KEY` (backend/.env). Si faltan, el broadcast
se degrada a un warning (la partida funciona igual de forma local — el jugador que actúa se
entera por la respuesta REST; el rival, por el broadcast). El frontend escucha `.on('broadcast',
{event: …})` en su canal `room:{code}`, que ya mantiene abierto por la presencia del lobby.
"""

from __future__ import annotations

import logging

import httpx

from backend.app.config import get_settings

log = logging.getLogger(__name__)

_TIMEOUT_S = 5.0


def _configured() -> bool:
    settings = get_settings()
    url = (settings.supabase_url or "").strip()
    key = (settings.supabase_anon_key or "").strip()
    if not url or url == "http://localhost" or not key:
        log.warning(
            "Broadcast Realtime deshabilitado: faltan SUPABASE_URL / SUPABASE_ANON_KEY en .env."
        )
        return False
    return True


async def broadcast(room_code: str, event: str, payload: dict) -> bool:
    """Envía `payload` como evento `event` al canal `room:{room_code}`.

    Devuelve `True` si Realtime lo aceptó. Nunca lanza: un fallo de broadcast no debe romper
    la petición que ya mutó el estado (el cliente autor aceita por su respuesta REST).
    """
    if not _configured():
        return False
    settings = get_settings()
    url = f"{settings.supabase_url}/realtime/v1/api/broadcast"
    body = {
        "messages": [
            {"topic": f"room:{room_code}", "event": event, "payload": payload},
        ]
    }
    headers = {"apikey": settings.supabase_anon_key, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            response = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        log.warning("Broadcast a room:%s falló (red): %s", room_code, exc)
        return False

    if response.status_code >= 400:
        log.warning(
            "Broadcast a room:%s rechazado por Realtime (%d): %s",
            room_code,
            response.status_code,
            response.text[:200],
        )
        return False
    return True