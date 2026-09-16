"""Analítica agregada. Toda la matemática vive en SQL, no en pandas.

Tres correcciones de raíz frente al monolito:
  1. `champion_performance` calcula `winrate` y `kda_ratio` (la UI las pedía y la query nunca las
     devolvía -> KeyError permanente en la Tab 3).
  2. Los agregados son promedios numéricos, nunca strings "K / D / A" que había que re-parsear.
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


async def champion_performance(user_id: str) -> list[dict[str, Any]]:
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
        WHERE user_id = %s AND {_NOT_A_REMAKE}
        GROUP BY champion
        ORDER BY games_played DESC, wins DESC
        """,
        (user_id,),
    )


# Un campeón con menos partidas no demuestra "dónde rindes": el winrate con 1-2 partidas es
# suerte, no tendencia. Este es el mínimo que separa ruido de señal en la vista de resumen.
_MIN_GAMES_FOR_ROLE_SUMMARY = 3


async def champion_role_summary(user_id: str) -> list[dict[str, Any]]:
    """Winrate/KDA por (campeón, rol, cola) con mínimo de 3 partidas.

    `matches.role` es el teamPosition del usuario en esa partida (equivalente al
    `team_position` del JSONB, pero a nivel de fila — una fila = una partida). Agrupar por
    las tres dimensiones deja ver dónde y en qué cola rindes, en vez de sumar ARAM con
    Solo/Duo o Top con mid.

    `delta_minutes` existe en la tabla desde la migración 002; las filas legacy con duración
    NULL se conservan (igual que en el resto de analítica) pero sin duración desconocida no
    hay "aprox." viable, así que `_NOT_A_REMAKE` aplica como en todos los paneles.
    """
    return await db.fetch_all(
        f"""
        SELECT
            champion,
            role,
            queue_id,
            COUNT(*)                                AS games_played,
            SUM(CASE WHEN win THEN 1 ELSE 0 END)    AS wins,
            SUM(CASE WHEN win THEN 0 ELSE 1 END)    AS losses,
            ROUND({_WINRATE}, 1)                    AS winrate,
            ROUND({_KDA_RATIO}, 2)                  AS kda_ratio
        FROM matches
        WHERE user_id = %s AND {_NOT_A_REMAKE}
          AND role IS NOT NULL AND role <> ''
          AND queue_id IS NOT NULL
        GROUP BY champion, role, queue_id
        HAVING COUNT(*) >= %s
        ORDER BY winrate DESC, games_played DESC
        """,
        (user_id, _MIN_GAMES_FOR_ROLE_SUMMARY),
    )


# ─────────────────────────────── Fatiga de sesión ───────────────────────────────

# Los umbrales de "autopilot": 20 puntos de winrate o -2.0 de KDA entre dos bloques de 5
# partidas. Conservadores a propósito — con una muestra tan corta un umbral laxo dispararía
# falsos positivos y el banner perdería crédito (grita "descansa" que no descansarás).
SESSION_RECENT_WINDOW = 5
SESSION_TOTAL_WINDOW = 10
FATIGUE_WINRATE_DROP_PP = 20.0
FATIGUE_KDA_DROP = 2.0


async def session_fatigue(user_id: str) -> dict[str, Any]:
    """Compara las últimas 5 partidas válidas contra las 5 anteriores para detectar autopilot.

    Las 10 partidas más recientes (sin remakes, con fecha) se parten por la mitad:
    `recent` = rn 1-5 (las más nuevas, en orden cronológico descendente), `previous` = rn 6-10.
    Con menos de 6 partidas almacenadas no hay bloque anterior y el diagnóstico solo dice
    "hacen falta más partidas".

    Ambos bloques se calculan en una sola pasada por SQL; el veredicto (fatiga sí/no y el
    mensaje) es lógica de negocio y vive en Python, no en la query.
    """
    rows = await db.fetch_all(
        f"""
        WITH ordenadas AS (
            SELECT
                win, kills, deaths, assists,
                ROW_NUMBER() OVER (ORDER BY date DESC) AS rn
            FROM matches
            WHERE user_id = %s AND {_NOT_A_REMAKE}
              AND date IS NOT NULL
            LIMIT %s
        ),
        bloques AS (
            SELECT
                CASE WHEN rn <= %s THEN 'recent' ELSE 'previous' END AS block,
                win, kills, deaths, assists
            FROM ordenadas
        )
        SELECT
            block,
            COUNT(*)                                AS games,
            SUM(CASE WHEN win THEN 1 ELSE 0 END)    AS wins,
            SUM(CASE WHEN win THEN 0 ELSE 1 END)    AS losses,
            ROUND({_WINRATE}, 1)                    AS winrate,
            ROUND({_KDA_RATIO}, 2)                  AS avg_kda
        FROM bloques
        GROUP BY block
        """,
        (user_id, SESSION_TOTAL_WINDOW, SESSION_RECENT_WINDOW),
    )

    blocks = {row["block"]: row for row in rows}
    recent = blocks.get("recent")
    previous = blocks.get("previous")

    result: dict[str, Any] = {
        "recent": recent,
        "previous": previous,
        "sample_ok": False,
        "winrate_delta_pp": None,
        "kda_delta": None,
        "fatigue_detected": False,
        "message": "",
    }

    if not recent:
        result["message"] = "Sin partidas válidas todavía: sincroniza y el análisis de sesión se activa solo."
        return result
    if not previous:
        result["message"] = (
            f"Necesitas más partidas: hay {recent['games']}/10 para el diagnóstico de fatiga de sesión."
        )
        return result

    winrate_delta_pp = round(float(recent["winrate"]) - float(previous["winrate"]), 1)
    kda_delta = round(float(recent["avg_kda"]) - float(previous["avg_kda"]), 2)
    result["winrate_delta_pp"] = winrate_delta_pp
    result["kda_delta"] = kda_delta

    total = recent["games"] + previous["games"]
    if total < SESSION_TOTAL_WINDOW:
        result["message"] = (
            f"Muestra parcial ({total}/10 partidas): con 10 el diagnóstico de autopilot es fiable."
        )
        return result

    result["sample_ok"] = True
    fatigue = (
        winrate_delta_pp <= -FATIGUE_WINRATE_DROP_PP
        or kda_delta <= -FATIGUE_KDA_DROP
    )
    result["fatigue_detected"] = fatigue

    if fatigue:
        causes = []
        if winrate_delta_pp <= -FATIGUE_WINRATE_DROP_PP:
            causes.append(f"winrate -{abs(winrate_delta_pp):.0f}pp")
        if kda_delta <= -FATIGUE_KDA_DROP:
            causes.append(f"KDA -{abs(kda_delta):.1f}")
        result["message"] = (
            f"Posible autopilot: el bloque reciente está en picado ({', '.join(causes)}). "
            "Considera cerrar la sesión o hacer una pausa de 15 minutos."
        )
    else:
        result["message"] = (
            f"Sin signos de fatiga: winrate {recent['winrate']}% vs {previous['winrate']}% "
            f"anterior, KDA {recent['avg_kda']} vs {previous['avg_kda']}."
        )
    return result


async def matchup(user_id: str, user_champion: str, enemy_champion: str) -> dict[str, Any]:
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
        WHERE user_id = %s
          AND LOWER(champion) = LOWER(%s)
          AND LOWER(enemy_champion) = LOWER(%s)
          AND {_NOT_A_REMAKE}
        """,
        (user_id, user_champion, enemy_champion),
    )
    return row or {
        "games_played": 0, "wins": 0, "losses": 0, "winrate": 0.0,
        "avg_kills": 0.0, "avg_deaths": 0.0, "avg_assists": 0.0, "kda_ratio": 0.0,
    }


_MIN_GAMES_FOR_BEST_WORST = 3

# Alerta de Parche: umbral de caída de winrate (puntos porcentuales) y mínimo de partidas
# en el parche actual para no dar un veredicto con una muestra irrisoria. 5 partidas: con 3,
# 0/3 vs 1/3 movía el winrate 33pp y disparaba falsos alertas ("0/5 vs 2/5" ya da una señal
# más estable sin ser una publicación estadística).
PATCH_DROP_THRESHOLD_PP = 4.0
MIN_PATCH_CURRENT_GAMES = 5
PATCH_POOL_SIZE = 3


async def activity_heatmap(timezone: str, user_id: str) -> dict[str, Any]:
    """Agregado día-de-semana x bloque horario (4 bloques de 6h), en la zona horaria de visualización.

    EXTRACT(DOW) -> 0 = domingo.
    Los bloques son: Madrugada (00-06), Mañana (06-12), Tarde (12-18), Noche (18-00).

    Devuelve ``cells`` (lista de filas), ``best_slot`` y ``worst_slot`` calculados con un
    umbral mínimo de ``_MIN_GAMES_FOR_BEST_WORST`` partidas por franja. Si ninguna franja
    supera el umbral, ambos campos son ``None``.
    """
    cells = await db.fetch_all(
        f"""
        WITH raw AS (
            SELECT
                CAST(EXTRACT(DOW  FROM date AT TIME ZONE %s) AS INTEGER) AS weekday,
                CAST(EXTRACT(HOUR FROM date AT TIME ZONE %s) AS INTEGER) AS hour,
                win
            FROM matches
            WHERE user_id = %s AND {_NOT_A_REMAKE}
              -- Fila legacy sin fecha: EXTRACT daría NULL y agruparía en una celda sintética
              -- `day_of_week=None` que Pydantic rechaza (<0 o >6) y tumbaría el endpoint entero.
              AND date IS NOT NULL
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
        (timezone, timezone, user_id),
    )

    eligible = [c for c in cells if c["games_played"] >= _MIN_GAMES_FOR_BEST_WORST]
    best_slot: dict[str, Any] | None = None
    worst_slot: dict[str, Any] | None = None
    if eligible:
        best_slot = max(eligible, key=lambda c: c["winrate"])
        worst_slot = min(eligible, key=lambda c: c["winrate"])

    return {"cells": cells, "best_slot": best_slot, "worst_slot": worst_slot}


async def lp_trend(
    user_id: str, limit: int = 20, queue_id: int | None = None
) -> list[dict[str, Any]]:
    """Últimas N partidas en orden cronológico ascendente, con el LP acumulado ya sumado en SQL.

    `lp_change` es NULL en las partidas aún no revisadas; se trata como 0 para que la línea no
    se corte, pero se expone `has_lp` para que el frontend pueda distinguir "0 LP" de "sin dato".

    Con `queue_id` la curva se acota a una cola (el gráfico pide 420): las normales/flex entran
    con lp_change NULL y contarlas como 0 LP aplana la tendencia Ranked — eso era mentirle al usuario.

    Sin filtro anti-remake a propósito: es el diario cronológico de reviews (dato subjetivo que
    el usuario registró), no estadística agregada; ocultarle partidas aquí sería mentirle.
    """
    where = "WHERE user_id = %s AND queue_id = %s" if queue_id is not None else "WHERE user_id = %s"
    params: tuple[Any, ...] = (user_id, limit) if queue_id is None else (user_id, queue_id, limit)
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


async def kpi_trend(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Serie temporal de KPIs de mejora de las últimas N partidas válidas (orden cronológico asc).

    Por partida devuelve CS/min y KDA desde las columnas de la fila, el DPM REAL del propio
    usuario desde su participante en el JSONB, su `kp` (kill participation almacenada al
    sincronizar) y el `vision_delta` contra su rival directo de línea.

    Para extraer los campos del JSONB se usa `JOIN LATERAL` (una sola pasada sobre el array
    `participants` por fila), en lugar de las subconsultas correlacionadas que recorrían el
    array hasta 4 veces. Las filas legacy sin `participants` producen NULL → el COALESCE
    exterior mantiene el comportamiento anterior (dpm=0, kp=NULL, vision_delta=NULL).

    `vision_delta` busca al participante enemigo con el mismo `team_position` en el equipo
    contrario y resta sus `vision_score` (usuario - rival). Sin rivales directos (ARAM, roles
    inválidos) devuelve `None`.

    Anti-remake sí en este endpoint: una rendición temprana distorsiona CS/min y muertes.
    """
    return await db.fetch_all(
        f"""
        WITH ultimas AS (
            SELECT
                m.game_id, m.date, m.cs_min, m.kills, m.deaths, m.assists,
                m.champion, m.win, m.game_duration_minutes, m.participants,
                me.p AS me
            FROM matches m
            LEFT JOIN LATERAL (
                SELECT p
                FROM jsonb_array_elements(m.participants) AS p
                WHERE LOWER(p->>'champion_name') = LOWER(m.champion)
                LIMIT 1
            ) AS me ON TRUE
            WHERE m.user_id = %s AND {_NOT_A_REMAKE}
            ORDER BY m.date DESC
            LIMIT %s
        )
        SELECT
            game_id,
            date                                            AS timestamp,
            COALESCE(ROUND(cs_min::numeric, 2), 0)          AS cs_min,
            COALESCE(ROUND(
                (me->>'total_damage')::numeric
                / GREATEST(game_duration_minutes, 1)
            , 0), 0)                                        AS dpm,
            ROUND((kills::numeric + assists::numeric) / GREATEST(deaths, 1), 2) AS kda,
            (
                (me->>'vision_score')::numeric - (
                    SELECT (enemy->>'vision_score')::numeric
                    FROM jsonb_array_elements(participants) AS enemy
                    WHERE enemy->>'team_id' <> me->>'team_id'
                      AND enemy->>'team_position' = me->>'team_position'
                      AND UPPER(me->>'team_position') NOT IN
                          ('', 'UNKNOWN', 'INVALID', 'NONE')
                    LIMIT 1
                )
            ) AS vision_delta,
            (me->>'kill_participation')::numeric            AS kp,
            win
        FROM ultimas
        ORDER BY date ASC
        """,
        (user_id, limit),
    )


async def patch_alert(user_id: str, current_patch: str) -> dict[str, Any]:
    """Compara el winrate de los `PATCH_POOL_SIZE` campeones más jugados entre el parche
    actual y los anteriores, para avisar de caídas de rendimiento tras un parche nuevo.

    El parche llega ya normalizado a "X.Y" (ej. "14.18"); `matches.game_version` guarda la
    versión completa de Riot ("14.18.586.6903") y se compara por los dos primeros componentes.
    Las filas con `game_version` NULL (legacy) no pueden ser del parche actual: cuentan como
    historial previo.

    Devuelve por campeón las partidas/winrate de cada lado y `delta_pp` (winrate actual -
    winrate previo, en puntos porcentuales). `dropped` marca si la caída supera
    `PATCH_DROP_THRESHOLD_PP` con al menos `MIN_PATCH_CURRENT_GAMES` partidas en el parche
    actual; con muestra insuficiente el campo queda False.

    `has_current_games` NO se limita al top-3: responde a si existe *cualquier* partida en el
    parche actual (p.ej. el usuario cambió de pool con el parche nuevo y el top-3 histórico no
    se ha jugado aún). Así el banner nunca afirma "parche sin partidas" cuando sí las hay.
    """
    rows = await db.fetch_all(
        f"""
        WITH pool AS (
            SELECT champion
            FROM matches
            WHERE user_id = %s AND {_NOT_A_REMAKE}
            GROUP BY champion
            ORDER BY COUNT(*) DESC, MAX(date) DESC
            LIMIT %s
        ),
        patched AS (
            SELECT
                m.champion,
                m.win,
                CASE
                    WHEN m.game_version IS NOT NULL
                         AND SPLIT_PART(m.game_version, '.', 1) || '.'
                             || SPLIT_PART(m.game_version, '.', 2) = %s
                    THEN 'current'
                    ELSE 'previous'
                END AS bucket
            FROM matches m
            JOIN pool ON pool.champion = m.champion
            WHERE m.user_id = %s AND {_NOT_A_REMAKE}
        )
        SELECT *
        FROM (
            SELECT
                champion,
                COUNT(*) FILTER (WHERE bucket = 'current')            AS games_current,
                COUNT(*) FILTER (WHERE bucket = 'current' AND win)    AS wins_current,
                COUNT(*) FILTER (WHERE bucket = 'previous')           AS games_previous,
                COUNT(*) FILTER (WHERE bucket = 'previous' AND win)   AS wins_previous,
                ROUND(
                    COUNT(*) FILTER (WHERE bucket = 'current' AND win)::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE bucket = 'current'), 0) * 100
                , 1)                                                  AS winrate_current,
                ROUND(
                    COUNT(*) FILTER (WHERE bucket = 'previous' AND win)::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE bucket = 'previous'), 0) * 100
                , 1)                                                  AS winrate_previous
            FROM patched
            GROUP BY champion
        ) ordenado
        ORDER BY games_previous + games_current DESC
        """,
        (user_id, PATCH_POOL_SIZE, current_patch, user_id),
    )

    # ¿Existe CUALQUIER partida en el parche actual? Independiente del pool: lo que importa es
    # no mostrar el aviso "parche nuevo sin partidas" si el usuario ya juega (aunque sea con
    # campeones fuera del top-3 histórico). Los remakes no validan nada, igual que en el pool.
    any_cell = await db.fetch_one(
        f"""
        SELECT COUNT(*) AS n
        FROM matches
        WHERE user_id = %s AND {_NOT_A_REMAKE}
          AND game_version IS NOT NULL
          AND SPLIT_PART(game_version, '.', 1) || '.' || SPLIT_PART(game_version, '.', 2) = %s
        """,
        (user_id, current_patch),
    )
    has_current_games = bool(any_cell and any_cell["n"] > 0)

    champions: list[dict[str, Any]] = []
    for row in rows:
        cur = row["winrate_current"]
        prev = row["winrate_previous"]
        delta = None
        if cur is not None and prev is not None:
            delta = round(float(cur) - float(prev), 1)
        dropped = bool(
            delta is not None
            and delta < -PATCH_DROP_THRESHOLD_PP
            and row["games_current"] >= MIN_PATCH_CURRENT_GAMES
        )
        champions.append({**row, "delta_pp": delta, "dropped": dropped})

    return {
        "current_patch": current_patch,
        "has_current_games": has_current_games,
        "champions": champions,
    }


# ─────────────────────────── Veredicto del meta ──────────────────────────────

# Regla de meta-shift: un emparejamiento "históricamente favorable" (winrate previo >= 55) que
# en el parche actual cae por debajo del 50%. Exigir MIN_META_CURRENT_GAMES evita declarar una
# mala racha de 1-2 partidas como "el meta cambió" — con una muestra así no hay parche que valga.
MIN_META_CURRENT_GAMES = 3
META_FAVORABLE_WR = 55.0
META_VERDICT_CUTOFF_WR = 50.0


def assess_meta_verdict_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convierte una fila del agregado SQL en un dict listo para `MetaVerdict`.

    Función pura (sin DB) para poder testear la regla de negocio de forma hermética: calcula
    los winrates de cada lado, el delta en puntos porcentuales y `meta_shift` con los umbrales
    definidos arriba. El SQL sólo agrupa y cuenta — el juicio vive aquí.
    """
    games_current = int(row["games_current"])
    games_previous = int(row["games_previous"])
    wins_current = int(row["wins_current"])
    wins_previous = int(row["wins_previous"])

    winrate_current: float | None = None
    if games_current > 0:
        winrate_current = round(wins_current / games_current * 100, 1)
    winrate_previous: float | None = None
    if games_previous > 0:
        winrate_previous = round(wins_previous / games_previous * 100, 1)

    delta_pp: float | None = None
    if winrate_current is not None and winrate_previous is not None:
        delta_pp = round(winrate_current - winrate_previous, 1)

    meta_shift = bool(
        games_current >= MIN_META_CURRENT_GAMES
        and winrate_previous is not None and winrate_previous >= META_FAVORABLE_WR
        and winrate_current is not None and winrate_current < META_VERDICT_CUTOFF_WR
    )
    return {
        **row,
        "winrate_current": winrate_current,
        "winrate_previous": winrate_previous,
        "delta_pp": delta_pp,
        "meta_shift": meta_shift,
    }


async def meta_verdict(user_id: str, current_patch: str) -> list[dict[str, Any]]:
    """Winrate por (tu campeón, campeón enemigo) separado por parche.

    El bucket se calcula igual que `patch_alert`: la `game_version` se normaliza a "X.Y" y se
    compara con el parche actual; las filas legacy con versión NULL cuentan como historial
    previo (nunca como parche actual). Los 'Unknown' de `enemy_champion` se descartan — no hay
    cruce que juzgar sin rival de línea.
    """
    rows = await db.fetch_all(
        f"""
        SELECT *
        FROM (
            SELECT
                champion                         AS user_champion,
                enemy_champion,
                COUNT(*) FILTER (WHERE bucket = 'current')          AS games_current,
                COUNT(*) FILTER (WHERE bucket = 'current' AND win)  AS wins_current,
                COUNT(*) FILTER (WHERE bucket = 'previous')         AS games_previous,
                COUNT(*) FILTER (WHERE bucket = 'previous' AND win) AS wins_previous
            FROM (
                SELECT
                    m.win,
                    m.champion,
                    m.enemy_champion,
                    CASE
                        WHEN m.game_version IS NOT NULL
                             AND SPLIT_PART(m.game_version, '.', 1) || '.'
                                 || SPLIT_PART(m.game_version, '.', 2) = %s
                        THEN 'current'
                        ELSE 'previous'
                    END AS bucket
                FROM matches m
                WHERE m.user_id = %s AND {_NOT_A_REMAKE}
                  AND enemy_champion IS NOT NULL AND enemy_champion <> 'Unknown'
            ) enfrentamientos
            GROUP BY champion, enemy_champion
        ) ordenado
        ORDER BY games_previous + games_current DESC
        """,
        (current_patch, user_id),
    )
    return [assess_meta_verdict_row(row) for row in rows]


# ─────────────────────────── Triángulo del Laning (Timeline) ──────────────────────

async def laning_summary(user_id: str, limit: int = 50) -> dict[str, Any]:
    """Promedios GD@15 / XPD@15 / CSD@15 de las últimas N partidas válidas.

    Lee del JSONB `participants` los campos nuevos `gd15`/`xpd15`/`csd15`, escritos por el
    sync al consumir el Timeline de Riot. Partidas sin esos campos (sincronizadas antes de
    esta feature, sin rival de línea directo, o con duración < 15 min) no entran en el
    promedio; `games_analyzed` refleja cuántas sí contaron.

    Anti-remake sí: una rendición temprana (< 5 min) no tiene un marco de 15 minutos real.
    """
    row = await db.fetch_one(
        f"""
        WITH ultimas AS (
            SELECT game_id, champion, participants
            FROM matches
            WHERE user_id = %s AND {_NOT_A_REMAKE}
            ORDER BY date DESC
            LIMIT %s
        )
        SELECT
            ROUND(AVG(l.gd15)::numeric, 1)  AS avg_gd15,
            ROUND(AVG(l.xpd15)::numeric, 1) AS avg_xpd15,
            ROUND(AVG(l.csd15)::numeric, 1) AS avg_csd15,
            COUNT(l.gd15)                   AS games_analyzed
        FROM ultimas u
        JOIN LATERAL (
            SELECT
                (p->>'gd15')::numeric  AS gd15,
                (p->>'xpd15')::numeric AS xpd15,
                (p->>'csd15')::numeric AS csd15
            FROM jsonb_array_elements(u.participants) AS p
            WHERE LOWER(p->>'champion_name') = LOWER(u.champion)
              AND (p->>'gd15') IS NOT NULL
            LIMIT 1
        ) AS l ON TRUE
        """,
        (user_id, limit),
    )
    return {
        "avg_gd15": row["avg_gd15"] if row else None,
        "avg_xpd15": row["avg_xpd15"] if row else None,
        "avg_csd15": row["avg_csd15"] if row else None,
        "games_analyzed": int(row["games_analyzed"]) if row else 0,
    }


# CTE compartida por las tres queries del reporte semanal: la ventana de los últimos 7
# días (date >= now - 7d, según UTC porque `date` se guarda en UTC) SIN remakes, de ESTE usuario.
_WEEK_CTE = """
    WITH week AS (
        SELECT *
        FROM matches
        WHERE user_id = %s
          AND date >= (NOW() - INTERVAL '7 days')
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


async def weekly_report(user_id: str) -> dict[str, Any]:
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
        """,
        (user_id,),
    ) or {}

    most_played = await db.fetch_one(
        f"""
        {cte}
        SELECT champion, COUNT(*) AS games, COUNT(*) FILTER (WHERE win) AS wins
        FROM week
        GROUP BY champion
        ORDER BY games DESC, wins DESC
        LIMIT 1
        """,
        (user_id,),
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
        """,
        (user_id,),
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
