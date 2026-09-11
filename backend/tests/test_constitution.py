"""Tests del motor de La Constitución (`services.constitution.evaluate_rules`).

El corazón del proyecto: en Streamlit vivía intestable dentro del sidebar, mezclado con
`st.error()`. Ahora es una función pura sin I/O — la configuración y las partidas entran como
parámetros — y el router es un wrapper de menos de 10 líneas. Cualquier regla nueva se testea
aquí, no al nivel del endpoint.
"""

from __future__ import annotations

from backend.app.services.constitution import evaluate_rules

MAX_DEATHS = 8.0
TARGET_CS_MIN = 7.0


def _m(win: bool, champion: str = "Jax", deaths: int = 3, cs_min: float = 7.0) -> dict:
    """Partida válida tal y como la devuelve `matches_repo.last_results`."""
    return {"win": win, "champion": champion, "deaths": deaths, "cs_min": cs_min}


def _eval(*matches):
    return evaluate_rules(
        champion_pool=["Jax", "Fiora"],
        max_deaths=MAX_DEATHS,
        target_cs_min=TARGET_CS_MIN,
        recent=list(matches),  # más reciente primero
    )


class TestGlobalStatus:
    def test_sin_partidas_no_data(self):
        result = evaluate_rules(champion_pool=[], max_deaths=MAX_DEATHS, target_cs_min=TARGET_CS_MIN, recent=[])
        assert result["global_status"] == "NO DATA"
        assert result["rules"] == []

    def test_todo_limpio_es_safe(self):
        result = _eval(_m(True), _m(True), _m(False))
        assert result["global_status"] == "SAFE TO PLAY"

    def test_fallo_dificil_fuerza_stop(self):
        result = _eval(_m(False, deaths=6), _m(False, deaths=9), _m(True))
        assert result["global_status"] == "STOP PLAYING (TILTED)"

    def test_solo_warning_queda_en_warning(self):
        # Muerte media > 80% del límite -> severity warning (status PASS), sin ningún FAIL.
        result = _eval(_m(True, deaths=7), _m(True, deaths=6), _m(True, deaths=7))
        assert result["global_status"] == "WARNING"
        assert any(r["severity"] == "warning" for r in result["rules"])

    def test_cs_fail_es_fail_duro(self):
        """Un FAIL (aunque sea severity 'warning') dispara el STOP: ése es el comportamiento
        actual del motor — CS bajo se trata como violación, no como aviso suave."""
        result = _eval(_m(True, cs_min=5.0), _m(True, cs_min=5.5), _m(True, cs_min=6.0))
        assert result["global_status"] == "STOP PLAYING (TILTED)"


class TestLossStreak:
    def test_dos_derrotas_seguidas_fallan(self):
        result = _eval(_m(False), _m(False), _m(True))
        rule = next(r for r in result["rules"] if r["rule"] == "loss_streak")
        assert rule["status"] == "FAIL"
        assert result["stats"]["consecutive_losses"] == 2

    def test_una_sola_derrota_no_para(self):
        result = _eval(_m(False), _m(True), _m(True))
        rule = next(r for r in result["rules"] if r["rule"] == "loss_streak")
        assert rule["status"] == "PASS"

    def test_derrotas_no_consecutivas_no_paran(self):
        result = _eval(_m(True), _m(False), _m(False))
        rule = next(r for r in result["rules"] if r["rule"] == "loss_streak")
        assert rule["status"] == "PASS"
        assert result["stats"]["consecutive_losses"] == 0


class TestChampionPool:
    def test_campeones_dentro_y_fuera_del_pool(self):
        ok = _eval(_m(True, "Jax"), _m(True, "Fiora"))
        assert next(r for r in ok["rules"] if r["rule"] == "pool_fidelity")["status"] == "PASS"

        off = _eval(_m(True, "Yasuo"), _m(True, "Jax"))
        rule = next(r for r in off["rules"] if r["rule"] == "pool_fidelity")
        assert rule["status"] == "FAIL"
        assert "Yasuo" in rule["message"]

    def test_insensible_a_mayusculas_y_espacios(self):
        result = _eval(_m(True, "jax"), _m(True, " JAX "))
        rule = next(r for r in result["rules"] if r["rule"] == "pool_fidelity")
        assert rule["status"] == "PASS"

    def test_pool_vacio_habilitado_deshabilita_la_regla(self):
        """Un pool llegado de un campo de texto vacío (`[""]`) NO debe marcar todo como off-pool."""
        result = evaluate_rules(
            champion_pool=["", "  "],
            max_deaths=MAX_DEATHS,
            target_cs_min=TARGET_CS_MIN,
            recent=[_m(True, "Yasuo")],
        )
        rule = next(r for r in result["rules"] if r["rule"] == "pool_fidelity")
        assert rule["status"] == "PASS"
        assert "deshabilitada" in rule["message"]


class TestDeathLimit:
    def test_muerte_media_superada_falla(self):
        result = _eval(_m(True, deaths=11), _m(True, deaths=9), _m(True, deaths=10))
        rule = next(r for r in result["rules"] if r["rule"] == "death_limit")
        assert rule["status"] == "FAIL"
        assert result["stats"]["avg_deaths"] == 10.0

    def test_cerca_del_limite_es_warning(self):
        result = _eval(_m(True, deaths=7), _m(True, deaths=6), _m(True, deaths=7))
        rule = next(r for r in result["rules"] if r["rule"] == "death_limit")
        assert rule["status"] == "PASS"
        assert rule["severity"] == "warning"

    def test_dentro_del_rango_pasa(self):
        result = _eval(_m(True, deaths=3), _m(True, deaths=4), _m(True, deaths=2))
        rule = next(r for r in result["rules"] if r["rule"] == "death_limit")
        assert rule["status"] == "PASS"
        assert rule["severity"] == "pass"


class TestFarming:
    def test_cs_bajo_objetivo_falla_con_warning(self):
        result = _eval(_m(True, cs_min=5.0), _m(True, cs_min=5.5), _m(True, cs_min=6.0))
        rule = next(r for r in result["rules"] if r["rule"] == "cs_farming")
        assert rule["status"] == "FAIL"
        assert rule["severity"] == "warning"

    def test_cs_en_rango_pasa(self):
        result = _eval(_m(True, cs_min=7.5), _m(True, cs_min=8.0), _m(True, cs_min=7.0))
        rule = next(r for r in result["rules"] if r["rule"] == "cs_farming")
        assert rule["status"] == "PASS"
        assert rule["severity"] == "pass"


class TestStats:
    def test_resumen_viaja_en_stats(self):
        result = _eval(_m(True), _m(False), _m(True))
        assert result["stats"]["games_analyzed"] == 3
        assert result["stats"]["wins"] == 2
        assert result["stats"]["losses"] == 1
        assert result["stats"]["avg_deaths"] == 3.0
        assert result["stats"]["avg_cs_min"] == 7.0