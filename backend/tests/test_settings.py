"""PUT /api/settings/riot: vinculación del Riot ID del usuario (v2.1 P1).

Hermético: el endpoint sólo persiste en `user_settings` (repo parcheado); la validez del
formato 'Nombre#TAG' y de la región viven en `RiotLinkRequest`, no en la UI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories import settings as settings_repo


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _row(riot_id: str = "Lucho#EUW", riot_region: str = "EUW1") -> dict:
    return {
        "champion_pool": ["Jax", "Fiora", "Camille"],
        "target_cs_min": 7.5,
        "max_deaths": 4.0,
        "target_dpm": 500,
        "target_kp_percent": 50,
        "target_vision_score": 20,
        "riot_id": riot_id,
        "riot_region": riot_region,
    }


def test_link_normaliza_riot_id_y_region(client, auth_headers, monkeypatch):
    async def _fake_update_riot(_user_id, riot_id, riot_region="EUW1"):
        return _row(riot_id, (riot_region or "EUW1").upper())

    monkeypatch.setattr(settings_repo, "update_riot", _fake_update_riot)

    r = client.put(
        "/api/settings/riot",
        headers=auth_headers,
        json={"riot_id": "  Lucho#EUW  ", "region": " euw1 "},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["riot_id"].strip() == "Lucho#EUW"
    assert body["riot_region"] == "EUW1"


def test_rechaza_riot_id_sin_tag(client, auth_headers):
    r = client.put("/api/settings/riot", headers=auth_headers, json={"riot_id": "Lucho"})
    assert r.status_code == 422
    assert "Nombre#TAG" in r.json()["detail"][0]["msg"]


def test_rechaza_tag_vacio(client, auth_headers):
    r = client.put(
        "/api/settings/riot",
        headers=auth_headers,
        json={"riot_id": "Lucho#", "region": "EUW1"},
    )
    assert r.status_code == 422


def test_rechaza_region_desconocida(client, auth_headers):
    r = client.put(
        "/api/settings/riot",
        headers=auth_headers,
        json={"riot_id": "Lucho#EUW", "region": "XYZ1"},
    )
    assert r.status_code == 422


def test_requiere_auth(client):
    r = client.put(
        "/api/settings/riot", json={"riot_id": "Lucho#EUW", "region": "EUW1"}
    )
    assert r.status_code == 401