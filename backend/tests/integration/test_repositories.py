"""Cobertura SQL real de repositories/ (auditoría 🔴: "Ninguna query de repositories/ en CI").

Cada test ejecuta un escenario completo contra el Postgres efímero: TRUNCATE → seed por la
misma ruta que usa producción (`insert_many`) → query del repositorio → aserción exacta.
Sin ORM, sin pandas, sin mocks de SQL: si una migración o una query se rompe, esto revienta.

Nota técnica: los repositorios son async y atan el pool al event loop que lo abre; cada
escenario corre con `asyncio.run` abriendo y cerrando el pool una vez. Es barato en localhost
y evita depender de la configuración de loops de pytest-asyncio.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from backend.app import db
from backend.app.repositories import matches as matches_repo
from backend.app.repositories import scout, stats

pytestmark = pytest.mark.integration


def run_scenario(scenario: Callable[[], Awaitable[Any]]) -> Any:
    """Abre pool → TRUNCATE → ejecuta el escenario → cierra pool. Un loop nuevo por test."""

    async def main() -> Any:
        await db.open_pool()
        try:
            # RESTART IDENTITY también resetea lp_snapshots por si un futuro test lo usa.
            await db.execute("TRUNCATE matches, lp_snapshots RESTART IDENTITY")
            return await scenario()
        finally:
            await db.close_pool()

    return asyncio.run(main())


_seq = {"n": 0}


def row(
    *,
    champion: str = "Jax",
    enemy: str | None = "Darius",
    queue: int = 420,
    duration: float | None = 30.0,
    win: bool = True,
    date: str,
    kills: int = 6,
    deaths: int = 3,
    assists: int = 8,
    cs_min: float = 7.3,
    participants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fila válida para insert_many (mismo vocabulario de columnas que producción)."""
    _seq["n"] += 1
    return {
        "game_id": f"EUW1_IT_{_seq['n']}",
        "date": date,
        "champion": champion,
        "role": "TOP",
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "cs_total": 220,
        "cs_min": cs_min,
        "control_wards": 2,
        "win": win,
        "enemy_champion": enemy,
        "game_duration_minutes": duration,
        "queue_id": queue,
        "participants": participants,
    }


def participant(champion: str, total_damage: int) -> dict[str, Any]:
    """Participante con las claves que las queries SQL leen del JSONB."""
    return {
        "puuid": f"puuid-{champion.lower()}",
        "player_name": "Lucho#EUW",
        "champion_name": champion,
        "kills": 6,
        "deaths": 3,
        "assists": 8,
        "cs": 220,
        "items": [],
        "summoner_spells": [4, 12],
        "team_id": 100,
        "team_position": "TOP",
        "win": True,
        "total_damage": total_damage,
        "total_damage_taken": 15000,
        "gold_earned": 13000,
        "vision_score": 22,
        "kill_participation": 0.7,
        "rating": 74.5,
    }


# ─────────────────────────── insert_many ───────────────────────────


def test_insert_many_es_idempotente():
    rows = [row(date="2026-08-01 18:00:00"), row(date="2026-08-02 18:00:00")]

    async def s() -> tuple[int, int, int]:
        primera = await matches_repo.insert_many(rows)
        segunda = await matches_repo.insert_many(rows)
        total = await matches_repo.count()
        return primera, segunda, total

    assert run_scenario(s) == (2, 0, 2)


# ─────────────────────────── list_recent (historial) ───────────────────────────


def test_list_recent_oculta_remakes_pero_conserva_legacy():
    remake = row(duration=2.0, date="2026-08-01 18:00:00")          # ranked corto → fuera
    legacy = row(duration=None, date="2026-08-02 18:00:00")         # NULL → visible (pre-esquema)
    ranked = row(duration=33.0, date="2026-08-03 18:00:00")         # ranked larga → visible
    flex = row(queue=440, duration=40.0, date="2026-08-04 18:00:00")

    async def s():
        await matches_repo.insert_many([remake, legacy, ranked, flex])
        todas = await matches_repo.list_recent(limit=50)
        ranked_view = await matches_repo.list_recent(limit=50, queue="ranked")
        normal_view = await matches_repo.list_recent(limit=50, queue="normal")
        return todas, ranked_view, normal_view

    todas, ranked_view, normal_view = run_scenario(s)

    ids_todas = [r["game_id"] for r in todas]
    # Orden DESC por fecha y sin el remake; el legacy (duración NULL) SÍ aparece.
    assert ids_todas == [flex["game_id"], ranked["game_id"], legacy["game_id"]]

    ids_ranked = {r["game_id"] for r in ranked_view}
    assert ids_ranked == {ranked["game_id"], legacy["game_id"]}
    assert all(r["queue_id"] in (420, 440) for r in ranked_view)

    # No hay partidas de colas 400/430 sembradas: la vista normal debe venir vacía.
    assert normal_view == []


def test_last_results_ventana_de_la_constitucion():
    derrota_valida = row(win=False, duration=28.0, date="2026-08-01 18:00:00")
    remake = row(duration=2.0, date="2026-08-02 18:00:00")            # <5 min → no cuenta
    normal_larga = row(queue=400, duration=35.0, date="2026-08-03 18:00:00")  # no es 420
    victoria_reciente = row(duration=41.0, date="2026-08-04 18:00:00")
    limite_exacto = row(duration=5.0, date="2026-08-05 18:00:00")     # frontera >= 5 → cuenta

    async def s():
        await matches_repo.insert_many(
            [derrota_valida, remake, normal_larga, victoria_reciente, limite_exacto]
        )
        return await matches_repo.last_results(limit=3)

    resultados = run_scenario(s)

    # Sólo ranked (420) con duración >= 5, más reciente primero. El remake y la normal fuera;
    # el límite exacto (5.0) entra porque la regla es >=.
    assert [r["game_id"] for r in resultados] == [
        limite_exacto["game_id"],
        victoria_reciente["game_id"],
        derrota_valida["game_id"],
    ]
    # Columnas que el motor de Constitución consume junto a esta ventana.
    assert set(resultados[0]) >= {"game_id", "date", "champion", "win", "deaths", "cs_min"}


# ─────────────────────────── stats.champion_performance ───────────────────────────


def test_champion_performance_dpm_real_desde_jsonb():
    jax_a = row(
        date="2026-08-01 18:00:00",
        duration=30.0,
        participants=[participant("Jax", total_damage=60000)],
    )
    jax_b = row(
        date="2026-08-02 18:00:00",
        duration=30.0,
        participants=[participant("Jax", total_damage=30000)],
    )
    katarina_legacy = row(champion="Katarina", date="2026-08-03 18:00:00", duration=25.0)

    async def s():
        await matches_repo.insert_many([jax_a, jax_b, katarina_legacy])
        return {r["champion"]: r for r in await stats.champion_performance()}

    filas = run_scenario(s)

    jax = filas["Jax"]
    # DPM REAL del JSONB: (60000/30 + 30000/30) / 2 = 1500. La fórmula legacy habría dado ~950:
    # si este número cambia sin tocar el JSONB, alguien reintrodujo la estimación.
    assert int(jax["avg_dpm"]) == 1500

    kat = filas["Katarina"]
    # Sin participants el CASE da NULL y el AVG la ignora: fila presente, DPM honestamente vacío.
    assert kat["games_played"] == 1
    assert kat["avg_dpm"] is None


# ─────────────────────────── stats.lp_trend ───────────────────────────


def test_lp_trend_acumulado_y_filtro_por_cola():
    derrota_ranked = row(win=False, date="2026-08-01 18:00:00")   # lp_change NULL abajo vía SQL
    normal = row(queue=400, date="2026-08-02 18:00:00")
    victoria_ranked = row(date="2026-08-03 18:00:00")

    async def s():
        await matches_repo.insert_many([derrota_ranked, normal, victoria_ranked])
        # lp_change directo: es un campo subjetivo que aquí simulamos ya revisado.
        await db.execute("UPDATE matches SET lp_change = -16 WHERE game_id = %s", (derrota_ranked["game_id"],))
        await db.execute("UPDATE matches SET lp_change = 15 WHERE game_id = %s", (victoria_ranked["game_id"],))

        filtrada = await stats.lp_trend(limit=10, queue_id=420)
        completa = await stats.lp_trend(limit=10)
        return filtrada, completa

    filtrada, completa = run_scenario(s)

    # Con filtro 420: sólo ranked, orden cronológico ASC, acumulado [-16, -1].
    assert [r["lp_cumulative"] for r in filtrada] == [-16, -1]
    assert [int(r["has_lp"]) for r in filtrada] == [1, 1]
    # La normal (400) quedó fuera: si entrara, el acumulado intermedio sería -1, no -16.
    assert len(filtrada) == 2

    # Sin filtro la normal entra como NULL→0: acumulado correcto pero aplanado entre medias.
    assert len(completa) == 3
    assert [r["lp_cumulative"] for r in completa] == [-16, -16, -1]


# ─────────────────────────── scout.nemesis ───────────────────────────


def test_nemesis_orden_exclusiones_y_antiremake():
    darius_1 = row(enemy="Darius", win=False, date="2026-08-01 18:00:00")
    darius_2 = row(enemy="Darius", win=False, date="2026-08-02 18:00:00")
    garen_w = row(enemy="Garen", win=True, date="2026-08-03 18:00:00")
    garen_l = row(enemy="Garen", win=False, date="2026-08-04 18:00:00")
    morde_remake = row(enemy="Mordekaiser", win=False, duration=2.0, date="2026-08-05 18:00:00")
    unknown_1 = row(enemy="Unknown", win=False, date="2026-08-06 18:00:00")
    unknown_2 = row(enemy="Unknown", win=False, date="2026-08-07 18:00:00")

    async def s():
        await matches_repo.insert_many(
            [darius_1, darius_2, garen_w, garen_l, morde_remake, unknown_1, unknown_2]
        )
        return await scout.nemesis(min_games=2, limit=5)

    enemigos = run_scenario(s)

    nombres = [e["enemy_champion"] for e in enemigos]
    # 'Darius' primero (0% wr), 'Garen' segundo (50%). 'Unknown' excluido por nombre y el
    # remake contra Mordekaiser no cuenta: con 1 partida real queda bajo min_games=2.
    assert nombres == ["Darius", "Garen"]
    assert float(enemigos[0]["winrate"]) == 0.0
    assert float(enemigos[1]["winrate"]) == 50.0
