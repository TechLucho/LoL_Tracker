"""Dependencias compartidas de FastAPI."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from backend.app.config import Settings, get_settings
from backend.app.services.riot import RiotService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_riot_service(settings: SettingsDep) -> RiotService:
    return RiotService(settings)


RiotServiceDep = Annotated[RiotService, Depends(get_riot_service)]


async def require_token(
    settings: SettingsDep,
    x_api_token: Annotated[str | None, Header()] = None,
) -> None:
    """Auth mínima para app mono-usuario.

    Si `APP_API_TOKEN` está vacío (uso local), no se exige nada. En cuanto se define —por ejemplo
    al desplegar en una VPS— pasa a ser obligatorio. La clave de Riot y las credenciales de DB
    nunca salen del backend en ninguno de los dos casos.

    La comparación usa `secrets.compare_digest` para prevenir ataques de timing: un atacante
    que mida el tiempo de respuesta no puede inferir cuántos bytes coinciden.
    """
    if not settings.app_api_token:
        return
    if x_api_token is None or not secrets.compare_digest(x_api_token, settings.app_api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o ausente (header X-API-Token).",
        )


AuthDep = Depends(require_token)
