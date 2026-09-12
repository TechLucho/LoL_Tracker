"""Validación de autenticación JWT en la capa HTTP.

Tests herméticos (sin DB) contra la capa de auth de FastAPI. Cubre:
  * sin header → 401
  * header no es Bearer → 401
  * token vacío / inválido / firma errónea → 401
  * token caducado → 401
  * sub ausente en claims → 401
  * token válido con user_id bien formado → 200

Usa `/api/health` (alias protegido del `/health` de diagnóstico) como endpoint sano de prueba.
"""

from __future__ import annotations

import datetime as dt
import uuid

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app

TEST_USER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sign(claims: dict, *, secret: str | None = None) -> str:
    """Firma claims con el secreto de la app (o uno arbitrario para tests de firma)."""
    secret = secret if secret is not None else get_settings().supabase_jwt_secret
    return pyjwt.encode(claims, secret, algorithm="HS256")


def _valid_claims(sub: uuid.UUID | str = TEST_USER_UUID) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "sub": str(sub),
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }


def test_sin_header_da_401(client):
    assert client.get("/api/health").status_code == 401


def test_bearer_vacio_da_401(client):
    assert client.get("/api/health", headers={"Authorization": ""}).status_code == 401


def test_bearer_no_es_jwt_da_401(client):
    assert client.get("/api/health", headers=_bearer("not-a-jwt")).status_code == 401


def test_token_firma_erronea_da_401(client):
    token = _sign(_valid_claims(), secret="wrong-secret-not-the-app-secret")
    assert client.get("/api/health", headers=_bearer(token)).status_code == 401


def test_token_caducado_da_401(client):
    claims = _valid_claims()
    claims["exp"] = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=60)
    token = _sign(claims)
    assert client.get("/api/health", headers=_bearer(token)).status_code == 401


def test_token_sin_sub_da_401(client):
    claims = _valid_claims()
    del claims["sub"]
    token = _sign(claims)
    assert client.get("/api/health", headers=_bearer(token)).status_code == 401


def test_sub_no_es_uuid_da_401(client):
    claims = _valid_claims(sub="no-es-un-uuid")
    token = _sign(claims)
    assert client.get("/api/health", headers=_bearer(token)).status_code == 401


def test_token_valido_da_200(client, auth_headers):
    r = client.get("/api/health", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")