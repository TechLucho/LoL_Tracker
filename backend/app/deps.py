"""Dependencias compartidas de FastAPI."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


_bearer_scheme = HTTPBearer(auto_error=False)

# Caché del cliente JWKS por URL de Supabase (migración 013 put public JWKS on every ES256
# token). PyJWKClient cachea internamente las claves recibidas; reutilizar la MISMA instancia
# entre peticiones evita re-descargar `/auth/v1/.well-known/jwks.json` en cada validación.
# `timeout` acota la descarga bloqueante: sin él urllib esperaría indefinidamente.
_JWKS_FETCH_TIMEOUT_S = 5
_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def _get_jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    uri = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    client = _jwks_clients.get(uri)
    if client is None:
        client = jwt.PyJWKClient(uri, timeout=_JWKS_FETCH_TIMEOUT_S)
        _jwks_clients[uri] = client
    return client


async def _resolve_signing_key(token: str, settings: Settings) -> str:
    """Devuelve la clave con la que verificar `token`, según el algoritmo anunciado por el header.

    Supabase firma sus tokens de sesión con HS256 (secreto compartido) o con ES256/RS256
    (JWKS pública). El modo de verificación se elige por token, de forma que un mismo backend
    acepta tokens de sesiones creadas antes y después de la rotación de Supabase:
      * `HS256`  → clave simétrica: `SUPABASE_JWT_SECRET` (bound to tests/hermético).
      * cualquier otro → JWKS pública de Supabase (`/auth/v1/.well-known/jwks.json`).
    """
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256":
        return settings.supabase_jwt_secret
    client = _get_jwks_client(settings.supabase_url)
    # El primer fetch de la JWKS es una red SÍNCRONA (urllib dentro de PyJWKClient): lanzarla
    # aquí bloquearía el event loop de uvicorn. Se descarga en un hilo del pool (to_thread);
    # la verificación ECDSA posterior es CPU pura y ya corre en el bucle, que es donde debe ser.
    signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
    return signing_key.key


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: SettingsDep,
) -> UUID:
    """Valida el JWT de sesión de Supabase y devuelve el `sub` (user_id de auth.users) como UUID.

    El frontend recibe el token de la sesión de Supabase y lo envía como `Authorization:
    Bearer <token>`. Verificación estricta:
      * firma validada según el algoritmo del token (HS256 con `SUPABASE_JWT_SECRET`, o
        ES256/RS256 contra la JWKS pública de `SUPABASE_URL`);
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
        key = await _resolve_signing_key(credentials.credentials, settings)
        claims = jwt.decode(
            credentials.credentials,
            key,
            # Según el algoritmo con el que venga firmado el token: HS256 (sesión antigua o
            # secreto compartido) y ES256/RS256 (sesiones firmadas con la JWKS de Supabase).
            algorithms=["HS256", "ES256", "RS256"],
            # Sin exigir `aud` (PyJWT lo validaría por defecto y rechazaría tokens sin ese claim).
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
    except jwt.PyJWKError:
        # La JWKS no se pudo descargar o no hay clave para el kid: imposible verificar. Sigue
        # siendo un 401 para el cliente (sin detalle que filtre) pero loggeado al detalle.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo verificar la firma del token.",
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