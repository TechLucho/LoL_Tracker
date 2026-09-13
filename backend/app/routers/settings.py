"""Vinculación de la cuenta Riot del usuario (v2.1 P1).

Mientras /api/config trocea champion pool y OKRs, vincular el Riot ID es un acto puntual
con validación propia: el onboarding de la v2.1 envía `{riot_id, region}` y este router lo
persiste en `user_settings` (migración 014). La validación del formato y la región ocurre
en `RiotLinkRequest` (schema), no en la UI. Tras el PUT, el frontend lanza el primer
`POST /api/sync` automáticamente.

El body de un PUT es idempotente; re-vincular pisa la vinculación anterior.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.deps import CurrentUserId
from backend.app.repositories import settings as repo
from backend.app.schemas import RiotLinkRequest, UserSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.put("/riot", response_model=UserSettings)
async def link_riot(user_id: CurrentUserId, payload: RiotLinkRequest) -> UserSettings:
    """Vincula (o re-vincula) el Riot ID del usuario.

    Mismo patrón de respuesta que PUT /api/config: devuelve la fila resultante ya
    normalizada (el validators del schema limpia `riot_id` y pasa `region` a mayúsculas).
    """
    row = await repo.update_riot(user_id, payload.riot_id, payload.region)
    return UserSettings(**row)