"""Analítica agregada. Toda la matemática vive en SQL, no en pandas.

Tres correcciones de raíz frente al monolito:
  1. `champion_performance` calcula `winrate` y `kda_ratio` (la UI las pedía y la query nunca las
     devolvía -> KeyError permanente en la Tab 3).
  2. `summary` devuelve promedios numéricos en vez de un string "K / D / A" que había que re-parsear.
  3. `avg_dpm` usa el daño REAL a campeones guardado en el JSONB `participants`; la fórmula legacy
     que lo estimaba desde kills/assists/CS mentía sistemáticamente al alza.
"""

from __future__ import annotations

from typing import Any

from backend.app import db

# (K + A) / D sobre totales, con GREATEST(...,1) para no dividir por cero en partidas sin muertes.
_KDA_RATIO = "(SUM(kills) + SUM(assists))::numeric / GREATEST(SUM(deaths), 1)"
_WINRATE = "SUM(CASE WHEN win THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100"

# Anti-remake: una partida de menos de 5 min (300 s) es una rendición temprana, no estadística;
# contamina winrates, KDA medio, CS/min y el heatmap. Se aplica en TODA query agregada. Las filas
# legacy con duración NULL (pre-migración del monolito) se conservan a propósito: duración
# desconocida no equivale a remake, y excluirlas borraría el historial antiguo de los paneles.
_NOT_A_REMAKE = "(game_duration_minutes IS NULL OR game_duration_minutes >= 5)"


async def summary() -> dict[str, Any]:
    row = await db.fetch_one(
        f"""
        SELECT
            COUNT(*)                                   AS total_games,
            COALESCE(SUM(CASE WHEN win THEN 1 ELSE 0 END), 0) AS total_wins,
            COALESCE(ROUND({_WINRATE}, 1), 0)          AS winrate,
            COALESCE(ROUND(AVG(kills)::numeric, 2), 0) AS avg_kills,
            COALESCE(ROUND(AVG(deaths)::numeric, 2), 0) AS avg_deaths,
            COALESCE(ROUND(AVG(assists)::numeric, 2), 0) AS avg_assists,
            COALESCE(ROUND({_KDA_RATIO}, 2), 0)        AS kda_ratio,
            COALESCE(ROUND(AVG(cs_min)::numeric, 2), 0) AS avg_cs_min
        FROM matches
        WHERE {_NOT_A_REMAKE}
        """
    )
    # Con la tabla vacía, COUNT(*) es 0 y los COALESCE dejan el resto en 0: nunca None.
    return row or {
        "total_games": 0, "total_wins": 0, "winrate": 0.0,
        "avg_kills": 0.0, "avg_deaths": 0.0, "avg_assists": 0.0,
        "kda_ratio": 0.0, "avg_cs_min": 0.0,
    }


# Daño por minuto REAL del propio usuario: se localiza su participante dentro del JSONB
# `participants` emparejando campeón (misma heurística que el frontend en MatchAccordion: una fila
# = una partida del usuario, así que el campeón lo identifica). Sin participants (filas legacy) o
# sin duración el CASE devuelve NULL y AVG lo ignora — no contamina con ceros falsos.
_DPM_REAL = """
            AVG(
                CASE
                    WHEN participants IS NOT NULL AND COALESCE(game_duration_minutes, 0) > 0 THEN (
                        SELECT (p->>'total_damage')::numeric / game_duration_minutes
                        FROM jsonb_array_elements(participants) AS p
                        WHERE LOWER(p->>'champion_name') = LOWER(champion)
                        LIMIT 1
                    )
                END
            )
"""


async def champion_performance() -> list[dict[str, Any]]:
    return await db.fetch_all(
        f"""
        SELECT
            champion,
            COUNT(*)                                AS games_played,
            SUM(CASE WHEN win THEN 1 ELSE 0 END)    AS wins,
            ROUND({_WINRATE}, 1)                    AS winrate,
            ROUND(AVG(kills)::numeric, 2)           AS avg_kills,
            ROUND(AVG(deaths)::numeric, 2)          AS avg_deaths,
            ROUND(AVG(assists)::numeric, 2)         AS avg_assists,
            ROUND({_KDA_RATIO}, 2)                  AS kda_ratio,
            ROUND(AVG(cs_min)::numeric, 2)          AS avg_cs_min,
            ROUND({_DPM_REAL}::numeric, 0)         AS avg_dpm
        FROM matches
        WHERE {_NOT_A_REMAKE}
        GROUP BY champion
        ORDER BY games_played DESC, wins DESC
        """
    )


async def matchup(user_champion: str, enemy_champion: str) -> dict[str, Any]:
    """Estadísticas del cruce de dos campeones, insensible a mayúsculas.

    Filtra por el campeón del usuario (`matches.champion`) contra el rival de línea
    (`matches.enemy_champion`). Con cero partidas devuelve una fila con todo a 0 para
    que la UI pueda pintar "0 partidas" y seguir permitiendo editar notas.
    """
    row = await db.fetch_one(
        f"""
        SELECT
            COUNT(*)                                AS games_played,
            SUM(CASE WHEN win THEN 1 ELSE 0 END)    AS wins,
            SUM(CASE WHEN win THEN 0 ELSE 1 END)    AS losses,
            ROUND({_WINRATE}, 1)                    AS winrate,
            ROUND(AVG(kills)::numeric, 2)           AS avg_kills,
            ROUND(AVG(deaths)::numeric, 2)          AS avg_deaths,
            ROUND(AVG(assists)::numeric, 2)         AS avg_assists,
            ROUND({_KDA_RATIO}, 2)                  AS kda_ratio
        FROM matches
        WHERE LOWER(champion) = LOWER(%s)
          AND LOWER(enemy_champion) = LOWER(%s)
          AND {_NOT_A_REMAKE}
        """,
        (user_champion, enemy_champion),
    )
    return row or {
        "games_played": 0, "wins": 0, "losses": 0, "winrate": 0.0,
        "avg_kills": 0.0, "avg_deaths": 0.0, "avg_assists": 0.0, "kda_ratio": 0.0,
    }


async def activity_heatmap(timezone: str) -> list[dict[str, Any]]:
    """Agregado día-de-semana x bloque horario (4 bloques de 6h), en la zona horaria de visualización.

    EXTRACT(DOW) -> 0 = domingo.
    Los bloques son: Madrugada (00-06), Mañana (06-12), Tarde (12-18), Noche (18-00).
    """
    return await db.fetch_all(
        f"""
        WITH raw AS (
            SELECT
                CAST(EXTRACT(DOW  FROM date AT TIME ZONE %s) AS INTEGER) AS weekday,
                CAST(EXTRACT(HOUR FROM date AT TIME ZONE %s) AS INTEGER) AS hour,
                win
            FROM matches
            WHERE {_NOT_A_REMAKE}
        ),
        blocked AS (
            SELECT
                weekday,
                CASE
                    WHEN hour >= 0  AND hour < 6  THEN 'Madrugada'
                    WHEN hour >= 6  AND hour < 12 THEN 'Mañana'
                    WHEN hour >= 12 AND hour < 18 THEN 'Tarde'
                    ELSE 'Noche'
                END AS time_block,
                win
            FROM raw
        )
        SELECT
            weekday                                   AS day_of_week,
            time_block,
            COUNT(*)                                  AS games_played,
            SUM(CASE WHEN win THEN 1 ELSE 0 END)      AS wins,
            SUM(CASE WHEN win THEN 0 ELSE 1 END)      AS losses,
            ROUND(
                SUM(CASE WHEN win THEN 1 ELSE 0 END)::numeric
                / GREATEST(COUNT(*), 1) * 100
            , 1)                                      AS winrate
        FROM blocked
        GROUP BY weekday, time_block
        ORDER BY weekday,
            CASE time_block
                WHEN 'Madrugada' THEN 1
                WHEN 'Mañana'    THEN 2
                WHEN 'Tarde'     THEN 3
                WHEN 'Noche'     THEN 4
            END
        """,
        (timezone, timezone),
    )


async def lp_trend(limit: int = 20, queue_id: int | None = None) -> list[dict[str, Any]]:
    """Últimas N partidas en orden cronológico ascendente, con el LP acumulado ya sumado en SQL.

    `lp_change` es NULL en las partidas aún no revisadas; se trata como 0 para que la línea no
    se corte, pero se expone `has_lp` para que el frontend pueda distinguir "0 LP" de "sin dato".

    Con `queue_id` la curva se acota a una cola (el gráfico pide 420): las normales/flex entran
    con lp_change NULL y contarlas como 0 LP aplana la tendencia Ranked — eso era mentirle al usuario.

    Sin filtro anti-remake a propósito: es el diario cronológico de reviews (dato subjetivo que
    el usuario registró), no estadística agregada; ocultarle partidas aquí sería mentirle.
    """
    where = "WHERE queue_id = %s" if queue_id is not None else ""
    params: tuple[Any, ...] = (limit,) if queue_id is None else (queue_id, limit)
    return await db.fetch_all(
        f"""
        WITH ultimas AS (
            SELECT game_id, date, champion, enemy_champion, win, lp_change
            FROM matches {where}
            ORDER BY date DESC LIMIT %s
        )
        SELECT
            game_id, date, champion, enemy_champion, win,
            lp_change,
            lp_change IS NOT NULL AS has_lp,
            SUM(COALESCE(lp_change, 0)) OVER (ORDER BY date ASC) AS lp_cumulative
        FROM ultimas
        ORDER BY date ASC
        """,
        params,
    )


async def kpi_trend(limit: int = 50) -> list[dict[str, Any]]:
    """Serie temporal de KPIs de mejora de las últimas N partidas válidas (orden cronológico asc).

    Por partida devuelve CS/min y KDA desde las columnas de la fila, y el DPM REAL del propio
    usuario desde su participante en el JSONB (misma heurística que `_DPM_REAL` agregada: empareja
    por campeón). Si una fila legacy no tiene participants, su DPM es NULL y la gráfica lo salta.

    Anti-remake sí en este endpoint: una rendición temprana distorsiona CS/min y muertes y no es
    un dato de evolución real.
    """
    return await db.fetch_all(
        f"""
        WITH ultimas AS (
            SELECT
                game_id, date, cs_min, kills, deaths, assists, champion,
                game_duration_minutes,
                participants,
                (
                    SELECT (p->>'total_damage')::numeric
                    FROM jsonb_array_elements(participants) AS p
                    WHERE LOWER(p->>'champion_name') = LOWER(champion)
                    LIMIT 1
                ) AS my_damage
            FROM matches
            WHERE {_NOT_A_REMAKE}
            ORDER BY date DESC
            LIMIT %s
        )
        SELECT
            game_id,
            date                                            AS timestamp,
            COALESCE(ROUND(cs_min::numeric, 2), 0)          AS cs_min,
            COALESCE(ROUND(
                (my_damage / GREATEST(game_duration_minutes, 1))::numeric
            , 0), 0)                                         AS dpm,
            ROUND((kills::numeric + assists::numeric) / GREATEST(deaths, 1), 2) AS kda
        FROM ultimas
        ORDER BY date ASC
        """,
        (limit,),
    )


# CTE compartida por las tres queries del reporte semanal: la ventana de los últimos 7
# días (date >= now - 7d, según UTC porque `date` se guarda en UTC) SIN remakes.
_WEEK_CTE = """
    WITH week AS (
        SELECT *
        FROM matches
        WHERE date >= (NOW() - INTERVAL '7 days')
          AND {not_a_remake}
    )
"""

# Rating 0-100 del propio usuario dentro del JSONB participants, emparejando por campeón.
_RATING_REAL = """
    (
        SELECT (p->>'rating')::numeric
        FROM jsonb_array_elements(participants) AS p
        WHERE LOWER(p->>'champion_name') = LOWER(champion)
        LIMIT 1
    )
"""


async def weekly_report() -> dict[str, Any]:
    """Resumen de la última semana (7 días según fecha UTC), para el "Reporte Semanal".

    Devuelve la agregación (partidas, winrate, KDA medio), el campeón más jugado y la mejor
    partida de la ventana (la de mayor rating del usuario). `rating` y el DPM se leen del
    JSONB participants; las filas legacy sin participants dan mejor_partida = None.

    El rating del usuario se localiza con la misma heurística que el resto del proyecto
    (el campeón de la fila identifica a su participante, porque cada fila es una partida
    del usuario).
    """
    cte = _WEEK_CTE.format(not_a_remake=_NOT_A_REMAKE)

    summary = await db.fetch_one(
        f"""
        {cte}
        SELECT
            (NOW() - INTERVAL '7 days')::date AS period_start,
            NOW()::date                        AS period_end,
            COUNT(*)                           AS total_games,
            COUNT(*) FILTER (WHERE win)        AS wins,
            COUNT(*) FILTER (WHERE NOT win)    AS losses,
            ROUND(
                COUNT(*) FILTER (WHERE win)::numeric / GREATEST(COUNT(*), 1) * 100
            , 1)                               AS winrate,
            ROUND(
                (SUM(kills)::numeric + SUM(assists)::numeric)
                / GREATEST(SUM(deaths), 1)
            , 2)                               AS avg_kda
        FROM week
        """
    ) or {}

    most_played = await db.fetch_one(
        f"""
        {cte}
        SELECT champion, COUNT(*) AS games, COUNT(*) FILTER (WHERE win) AS wins
        FROM week
        GROUP BY champion
        ORDER BY games DESC, wins DESC
        LIMIT 1
        """
    )

    best_match = await db.fetch_one(
        f"""
        {cte}
        SELECT
            game_id, date, champion, kills, deaths, assists,
            {_RATING_REAL}                                   AS rating,
            ROUND(
                (kills::numeric + assists::numeric) / GREATEST(deaths, 1)
            , 2)                                             AS kda
        FROM week
        WHERE {_RATING_REAL} IS NOT NULL
        ORDER BY rating DESC
        LIMIT 1
        """
    )

    # Fallback seguro: sin partidas en la ventana, SUM(...) devuelve nulos (p.ej. avg_kda)
    # y COUNT necesita partir de 0. Nunca dejar que lleguen None a Pydantic.
    base = {
        **summary,
        "total_games": summary.get("total_games") or 0,
        "wins": summary.get("wins") or 0,
        "losses": summary.get("losses") or 0,
        "winrate": summary.get("winrate") or 0.0,
        "avg_kda": summary.get("avg_kda") or 0.0,
    }

    return {
        **base,
        "most_played": most_played,
        "best_match": best_match,
    }
