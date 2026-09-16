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

# v2.0 (migración 013): las tablas transaccionales pertenecen a un usuario y las políticas RLS
# se definen sobre `auth.users`. El Postgres de CI/efímero usa el stub de la migración 013; toda
# la cobertura sembra y consulta bajo ESTE user_id. `_OTHER_USER` existe para el aislamiento.
USER = "00000000-0000-0000-0000-000000000001"
OTHER_USER = "00000000-0000-0000-0000-000000000002"


def run_scenario(scenario: Callable[[], Awaitable[Any]]) -> Any:
    """Abre pool → TRUNCATE → siembra el usuario stub → ejecuta el escenario → cierra pool."""

    async def main() -> Any:
        await db.open_pool()
        try:
            # RESTART IDENTITY también resetea lp_snapshots por si un futuro test lo usa.
            # scout_cache se trunca para que el roundtrip del escout parta siempre de vacío.
            await db.execute(
                "TRUNCATE matches, user_settings, sync_runs, matchup_notes, "
                "lp_snapshots, scout_cache RESTART IDENTITY"
            )
            # auth.users es el stub de la migración 013 en CI (no-op en Supabase real: las
            # filas de verdad las crea el auth de Supabase). Sin esta siembra el FK de
            # `user_id` rechazaría cualquier INSERT.
            await db.execute(
                "INSERT INTO auth.users (id) VALUES (%s), (%s) ON CONFLICT (id) DO NOTHING",
                (USER, OTHER_USER),
            )
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
        primera = await matches_repo.insert_many(USER, rows)
        segunda = await matches_repo.insert_many(USER, rows)
        total = len(await matches_repo.list_recent(USER, limit=100))
        return primera, segunda, total

    assert run_scenario(s) == (2, 0, 2)


# ─────────────────────────── list_recent (historial) ───────────────────────────


def test_list_recent_oculta_remakes_pero_conserva_legacy():
    remake = row(duration=2.0, date="2026-08-01 18:00:00")          # ranked corto → fuera
    legacy = row(duration=None, date="2026-08-02 18:00:00")         # NULL → visible (pre-esquema)
    ranked = row(duration=33.0, date="2026-08-03 18:00:00")         # ranked larga → visible
    flex = row(queue=440, duration=40.0, date="2026-08-04 18:00:00")

    async def s():
        await matches_repo.insert_many(USER, [remake, legacy, ranked, flex])
        todas = await matches_repo.list_recent(USER, limit=50)
        ranked_view = await matches_repo.list_recent(USER, limit=50, queue="ranked")
        normal_view = await matches_repo.list_recent(USER, limit=50, queue="normal")
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
            USER,
            [derrota_valida, remake, normal_larga, victoria_reciente, limite_exacto],
        )
        return await matches_repo.last_results(USER, limit=3)

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
        await matches_repo.insert_many(USER, [jax_a, jax_b, katarina_legacy])
        return {r["champion"]: r for r in await stats.champion_performance(USER)}

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
        await matches_repo.insert_many(USER, [derrota_ranked, normal, victoria_ranked])
        # lp_change directo: es un campo subjetivo que aquí simulamos ya revisado.
        await db.execute("UPDATE matches SET lp_change = -16 WHERE game_id = %s", (derrota_ranked["game_id"],))
        await db.execute("UPDATE matches SET lp_change = 15 WHERE game_id = %s", (victoria_ranked["game_id"],))

        filtrada = await stats.lp_trend(USER, limit=10, queue_id=420)
        completa = await stats.lp_trend(USER, limit=10)
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


# ─────────────────────────── stats.laning_summary ───────────────────────────


def test_laning_summary_promedia_jsonb_y_ignora_sin_datos():
    """El triángulo del laning se lee del JSONB del propio usuario y sólo cuenta partidas
    con datos de Timeline (remakes y filas antiguas fuera)."""
    g1 = row(
        date="2026-08-01 18:00:00",
        participants=[{**participant("Jax", 60000), "gd15": 300, "xpd15": 200, "csd15": 3}],
    )
    g2 = row(
        champion="Yasuo", enemy="Irelia",
        date="2026-08-02 18:00:00",
        participants=[{**participant("Yasuo", 30000), "gd15": -100, "xpd15": 50, "csd15": -2}],
    )
    sin_datos = row(
        champion="Garen", enemy="Darius",
        date="2026-08-03 18:00:00",
        participants=[participant("Garen", 20000)],  # sin gd15/xpd15/csd15
    )
    remake = row(
        duration=2.0,
        date="2026-08-04 18:00:00",
        participants=[{**participant("Jax", 0), "gd15": 999, "xpd15": 999, "csd15": 9}],
    )

    async def s():
        await matches_repo.insert_many(USER, [g1, g2, sin_datos, remake])
        return await stats.laning_summary(USER, limit=50)

    result = run_scenario(s)

    # Sólo g1 y g2 entran: (300 + (-100))/2 = 100, (200+50)/2 = 125, (3 + -2)/2 = 0.5
    assert float(result["avg_gd15"]) == 100.0
    assert float(result["avg_xpd15"]) == 125.0
    assert float(result["avg_csd15"]) == 0.5
    assert result["games_analyzed"] == 2


def test_laning_summary_sin_partidas_con_datos_reporta_cero():
    remakes = [row(duration=2.0, date=f"2026-08-0{i} 18:00:00") for i in range(1, 4)]

    async def s():
        await matches_repo.insert_many(USER, remakes)
        return await stats.laning_summary(USER, limit=50)

    result = run_scenario(s)
    assert result == {"avg_gd15": None, "avg_xpd15": None, "avg_csd15": None, "games_analyzed": 0}


def test_scout_cache_roundtrip_positivo_y_negativo():
    """La caché del escout persiste payload y error por separado, y el upsert por puuid es coherente."""

    async def s():
        payload = [{"champion": "Jax", "champion_key": "63", "mastery_level": 7, "points": 400_000}]

        # Caché positiva: set -> get devuelve payload y sin error.
        await scout.set_scout_cache("p-rival", payload)
        out_payload, cached_at, error = await scout.get_scout_cache("p-rival")
        assert out_payload == payload
        assert error == ""
        assert cached_at is not None

        # Caché negativa: el mismo puuid se sobrescribe con el estado fallido.
        await scout.set_scout_cache_error("p-rival", "Rate limit de Riot excedido.")
        out_payload2, cached_at2, error2 = await scout.get_scout_cache("p-rival")
        assert out_payload2 == []
        assert error2 == "Rate limit de Riot excedido."
        assert cached_at2 >= cached_at

        # Un rival distinto no colisiona con el de arriba (miss limpio).
        assert await scout.get_scout_cache("p-otro") == (None, None, "")

    return run_scenario(s)


# ─────────────────────────── aislamiento por usuario (v2.0) ───────────────────────────


def test_aislamiento_entre_usuarios():
    """Los datos del USER no deben aparecer en las lecturas de OTHER_USER, ni al revés.

    Es el contrato que impone la migración 013 + RLS a nivel de query de repositorio: si
    alguien reintroduce una query global sin `user_id`, el agregado de un usuario se filtra
    a otro y este test revienta.
    """
    mina = [
        row(champion="Jax", enemy="Darius", win=True, date="2026-08-01 18:00:00"),
        row(champion="Jax", enemy="Darius", win=False, date="2026-08-02 18:00:00"),
    ]
    suya = [
        row(champion="Yasuo", enemy="Irelia", win=True, date="2026-08-01 18:00:00"),
    ]

    async def s() -> dict[str, Any]:
        await matches_repo.insert_many(USER, mina)
        await matches_repo.insert_many(OTHER_USER, suya)

        # list_recent: cada uno ve sólo sus partidas.
        ids_mios = [m["game_id"] for m in await matches_repo.list_recent(USER, limit=50)]
        assert all(m["game_id"] in ids_mios for m in mina)
        assert suya[0]["game_id"] not in ids_mios

        ids_del_otro = [m["game_id"] for m in await matches_repo.list_recent(OTHER_USER, limit=50)]
        assert len(ids_del_otro) == 1

        # last_results: ventana de La Constitución de USER sin filas ajenas.
        ventana = await matches_repo.last_results(USER, limit=3)
        assert len(ventana) == 2

        return {}

    run_scenario(s)
