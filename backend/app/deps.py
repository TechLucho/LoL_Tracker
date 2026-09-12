"""Dependencias compartidas de FastAPI."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import Settings, get_settings
from backend.app.services.riot import RiotService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_riot_service(settings: SettingsDep) -> RiotService:
    return RiotService(settings)


RiotServiceDep = Annotated[RiotService, Depends(get_riot_service)]


_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: SettingsDep,
) -> UUID:
    """Valida el JWT de sesión de Supabase y devuelve el `sub` (user_id de auth.users) como UUID.

    El frontend recibe el token de la sesión de Supabase y lo envía como `Authorization:
    Bearer <token>`. Verificación estricta:
      * firma HS256 contra `SUPABASE_JWT_SECRET` (rota el secreto en Supabase = tokens muertos);
      * claim `exp` (PyJWT lo valida automáticamente si está presente, y Supabase lo incluye);
      * `sub` presente y convertible a UUID — es el user_id que ya hace de clave de todas las
        tablas transaccionales (migración 013 y RLS).

    Cualquier fallo en firma, formato o expiración → 401, sin distinción de motivos al cliente.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación ausente (header Authorization: Bearer <token>).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            # Verificación ceñida al contrato interno: firma HS256 + `exp` + `sub`. Sin
            # exigir `aud` (PyJWT lo validaría por defecto y rechazaría tokens sin ese claim).
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    raw_sub = claims.get("sub")
    try:
        return UUID(str(raw_sub))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no incluye un `sub` (user_id) válido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


CurrentUserId = Annotated[UUID, Depends(get_current_user)]