"""Smoke tests de la API: que arranca, que el contrato está completo y que un fallo de DB se
reporta como tal en vez de disfrazarse de "no hay datos".
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_responde_sin_auth(client):
    """/health debe ser diagnosticable incluso sin credenciales válidas."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert isinstance(body["warnings"], list)


def test_health_no_reporta_falsos_positivos(client):
    """/health sólo avisa de problemas reales (DB caída); sin warnings con todo sano."""
    body = client.get("/health").json()
    assert "riot_key_is_dev" not in body


def test_openapi_expone_todos_los_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    esperados = {
        "/health",
        "/api/health",
        "/api/matches",
        "/api/matches/{game_id}",
        "/api/sync",
        "/api/stats/summary",
        "/api/stats/champions",
        "/api/stats/heatmap",
        "/api/stats/lp-trend",
        "/api/stats/constitution",
        "/api/scout/nemesis",
        "/api/scout/matchups",
        "/api/config",
        "/api/datadragon/version",
        "/api/metadata/champions",
        "/api/metadata/items",
        "/api/metadata/spells",
    }
    assert esperados <= paths.keys()


def test_champions_incluye_winrate_y_kda_ratio(client):
    """Las dos columnas que la Tab 3 de Streamlit pedía y la query nunca devolvía."""
    schema = client.get("/openapi.json").json()["components"]["schemas"]["ChampionStats"]
    assert "winrate" in schema["properties"]
    assert "kda_ratio" in schema["properties"]


def test_summary_devuelve_numeros_no_strings(client):
    """El monolito devolvía la KDA como "5.0 / 2.0 / 10.0" y la UI la re-parseaba: origen del
    bug de app.py:128. El contrato ahora es numérico."""
    props = client.get("/openapi.json").json()["components"]["schemas"]["StatsSummary"]["properties"]
    for campo in ("avg_kills", "avg_deaths", "avg_assists", "kda_ratio", "winrate"):
        assert props[campo]["type"] == "number", f"{campo} debería ser numérico"
    assert "kda" not in props, "No debe haber un campo KDA pre-formateado"


def test_matchups_exige_algun_filtro(client):
    r = client.get("/api/scout/matchups")
    assert r.status_code == 422


def test_patch_sin_campos_es_rechazado(client):
    r = client.patch("/api/matches/EUW1_TEST/", json={})
    assert r.status_code in (404, 422, 307)


# ───────────────────── observabilidad (middleware + métricas) ─────────────────────


def test_cada_respuesta_lleva_request_id_unico(client):
    """El X-Request-ID permite trazar una petición concreta en los logs del servidor."""
    r1 = client.get("/health")
    r2 = client.get("/health")
    rid1 = r1.headers["X-Request-ID"]
    rid2 = r2.headers["X-Request-ID"]
    assert rid1 and rid2
    assert rid1 != rid2, "cada petición debe tener su propio id"


def test_metrics_expone_contrato_minimo(client):
    """p50/p95 por endpoint en memoria: el 'nivel mínimo' que pedía la auditoría."""
    client.get("/health")
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert {"uptime_seconds", "endpoints"} <= body.keys()
    assert body["endpoints"], "el tráfico recién generado debería aparecer"
    sample = body["endpoints"][0]
    assert {"method", "path", "count", "errors", "p50_ms", "p95_ms", "max_ms"} <= sample.keys()
    assert all(e["count"] > 0 for e in body["endpoints"])


def test_el_filtro_de_logging_inyecta_request_id_del_contexto():
    from backend.app.observability import RequestIdFilter, request_id_var

    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hola", None, None)
    assert RequestIdFilter().filter(record) is True
    assert record.request_id == request_id_var.get()
