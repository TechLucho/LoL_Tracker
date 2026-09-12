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


def test_token_es256_via_jwks_da_200(client, monkeypatch):
    """Supabase rota a ES256: la clave llega de la JWKS, no del secreto compartido."""
    from types import SimpleNamespace

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from backend.app import deps as deps_mod
    from backend.app.config import get_settings

    private_key = ec.generate_private_key(ec.SECP256R1())
    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    token = pyjwt.encode(_valid_claims(), private_key, algorithm="ES256", headers={"kid": "test"})

    uri = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
    fake_jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=pub_pem))
    monkeypatch.setitem(deps_mod._jwks_clients, uri, fake_jwks)

    r = client.get("/api/health", headers=_bearer(token))
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")


def test_token_es256_clave_equivocada_da_401(client, monkeypatch):
    """La JWKS devuelve otra clave pública: la firma no verifica y el token cae en 401."""
    from types import SimpleNamespace

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from backend.app import deps as deps_mod
    from backend.app.config import get_settings

    private_key = ec.generate_private_key(ec.SECP256R1())
    other_pub = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    token = pyjwt.encode(_valid_claims(), private_key, algorithm="ES256", headers={"kid": "test"})

    uri = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
    fake_jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=other_pub))
    monkeypatch.setitem(deps_mod._jwks_clients, uri, fake_jwks)

    r = client.get("/api/health", headers=_bearer(token))
    assert r.status_code == 401