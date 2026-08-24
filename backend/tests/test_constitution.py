"""Tests de La Constitución.

Estas reglas son el corazón del proyecto y en Streamlit eran intestables: vivían dentro del
sidebar, mezcladas con llamadas a `st.error()`. Ahora son una función pura.
"""

from __future__ import annotations

from backend.app.services.constitution import evaluate, is_off_pool


def _m(*wins: bool) -> list[dict]:
    """Partidas, más reciente primero."""
    return [{"win": w} for w in wins]


class TestEvaluate:
    def test_sin_partidas(self):
        result = evaluate([])
        assert result["state"] == "NO_DATA"
        assert result["loss_streak"] == 0

    def test_dos_derrotas_seguidas_obliga_a_parar(self):
        result = evaluate(_m(False, False, True))
        assert result["state"] == "STOP"
        assert result["loss_streak"] == 2

    def test_tres_derrotas_seguidas_sigue_siendo_stop(self):
        result = evaluate(_m(False, False, False))
        assert result["state"] == "STOP"
        assert result["loss_streak"] == 3

    def test_una_sola_derrota_no_para(self):
        result = evaluate(_m(False, True, True))
        assert result["state"] == "NEUTRAL"
        assert result["loss_streak"] == 1

    def test_tres_de_tres_es_on_fire(self):
        result = evaluate(_m(True, True, True))
        assert result["state"] == "ON_FIRE"
        assert result["loss_streak"] == 0

    def test_dos_victorias_no_bastan_para_on_fire(self):
        """Con sólo 2 partidas jugadas no se puede afirmar 3/3."""
        result = evaluate(_m(True, True))
        assert result["state"] == "NEUTRAL"

    def test_derrotas_no_consecutivas_no_paran(self):
        result = evaluate(_m(True, False, False))
        assert result["state"] == "NEUTRAL"
        assert result["loss_streak"] == 0

    def test_solo_mira_el_bloque_de_tres(self):
        """Una cuarta partida no debe influir: la regla es por bloques de 3."""
        result = evaluate(_m(True, True, True, False))
        assert result["state"] == "ON_FIRE"
        assert result["last_results"] == [True, True, True]


class TestChampionPool:
    def test_campeon_dentro_del_pool(self):
        assert is_off_pool("Jax", ["Jax", "Fiora", "Camille"]) is False

    def test_campeon_fuera_del_pool(self):
        assert is_off_pool("Yasuo", ["Jax", "Fiora", "Camille"]) is True

    def test_comparacion_insensible_a_mayusculas_y_espacios(self):
        assert is_off_pool("jax", [" JAX ", "Fiora"]) is False

    def test_pool_vacio_no_alerta(self):
        """Sin pool declarado no hay nada que incumplir."""
        assert is_off_pool("Yasuo", []) is False
        assert is_off_pool("Yasuo", ["", "  "]) is False
