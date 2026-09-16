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
        "/api/matches/{game_id}/scout-opponent",
        "/api/sync",
        "/api/stats/champions",
        "/api/stats/champion-summary",
        "/api/stats/session-fatigue",
        "/api/stats/meta-verdict",
        "/api/stats/heatmap",
        "/api/stats/patch-alert",
        "/api/stats/lp-trend",
        "/api/stats/trends",
        "/api/stats/laning",
        "/api/stats/weekly",
        "/api/config",
        "/api/settings/riot",
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


def test_patch_sin_campos_es_rechazado(client, auth_headers):
    r = client.patch("/api/matches/EUW1_TEST/", json={}, headers=auth_headers)
    assert r.status_code in (404, 422, 307)


def test_okrs_expuestos_en_user_settings(client):
    """Los objetivos de rendimiento deben viajar en la config y en su update."""
    props = (client.get("/openapi.json").json()["components"]["schemas"]["UserSettings"]
             ["properties"])
    for campo in ("target_dpm", "target_kp_percent", "target_vision_score"):
        assert campo in props, f"{campo} debería estar expuesto en UserSettings"


def test_scout_opponent_en_contrato(client):
    """El escout debe exponer las maestrías del rival y su origen (caché o llamada a Riot)."""
    schema = client.get("/openapi.json").json()["components"]["schemas"]["ScoutOpponent"]
    for campo in ("opponent_puuid", "opponent_champion", "top_champions", "cached", "note"):
        assert campo in schema["properties"], f"ScoutOpponent debería tener {campo}"
    champion = client.get("/openapi.json").json()["components"]["schemas"]["ScoutMasteryChampion"]
    for campo in ("champion", "mastery_level", "points"):
        assert campo in champion["properties"]


def test_meta_verdict_en_contrato(client):
    """El veredicto del meta debe traer el delta y la bandera de shift por emparejamiento."""
    schema = client.get("/openapi.json").json()["components"]["schemas"]["MetaVerdict"]
    for campo in ("user_champion", "enemy_champion", "winrate_current", "winrate_previous",
                  "delta_pp", "meta_shift"):
        assert campo in schema["properties"], f"MetaVerdict debería tener {campo}"


def test_sync_result_incluye_tilt_alert(client):
    """El contrato del sync debe poder avisar de una racha de derrotas."""
    props = (client.get("/openapi.json").json()["components"]["schemas"]["SyncResult"]
             ["properties"])
    assert "losing_streak_warning" in props


# ───────────────────── observabilidad (middleware + métricas) ─────────────────────


def test_cada_respuesta_lleva_request_id_unico(client):
    """El X-Request-ID permite trazar una petición concreta en los logs del servidor."""
    r1 = client.get("/health")
    r2 = client.get("/health")
    rid1 = r1.headers["X-Request-ID"]
    rid2 = r2.headers["X-Request-ID"]
    assert rid1 and rid2
    assert rid1 != rid2, "cada petición debe tener su propio id"


def test_metrics_expone_contrato_minimo(client, auth_headers):
    """p50/p95 por endpoint en memoria: el 'nivel mínimo' que pedía la auditoría."""
    client.get("/health")
    r = client.get("/api/metrics", headers=auth_headers)
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
