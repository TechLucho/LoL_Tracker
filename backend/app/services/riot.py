"""Cliente de la API de Riot (Account-V1 + Match-V5).

Diferencias clave frente a `riot_client.py`:

  * **Los 429 ya no se pierden.** El monolito envolvía el procesado de cada partida en un
    `except Exception: continue`, así que un rate limit se trataba igual que un JSON corrupto:
    la partida se descartaba en silencio y la UI reportaba éxito. Aquí se reintenta con backoff
    y, si aun así falla, el error viaja en la respuesta del sync.
  * **PUUID cacheado.** Antes se resolvía el Riot ID en *cada* descarga (una llamada de más
    por sync, gastando cuota).
  * **Timestamps en UTC.** Antes se usaba la hora local del host, lo que hacía que el heatmap
    "biológico" cambiara de significado según la máquina.
  * **Nombres de columna finales.** Emite `champion` y `control_wards`, no `champion_name` y
    `control_wards_bought`, para que no haya dos vocabularios entre API y DB.
  * **Rating universal en backend.** El 0-100 que antes calculaba el frontend sólo para el
    jugador principal se aplica aquí a los 10 participantes (`calculate_participant_rating`),
    de modo que el JSONB ya guarda la puntuación lista para el rediseño de la pestaña Match.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any

from fastapi.concurrency import run_in_threadpool
from riotwatcher import ApiError, LolWatcher, RiotWatcher

from backend.app.config import Settings
from backend.app.schemas import RATING_VERSION

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2.0
# Techo al Retry-After que dicta Riot: una cabecera exótica no debe colgar el sync minutos.
MAX_RETRY_AFTER_SECONDS = 120.0
PUUID_CACHE_TTL_SECONDS = 24 * 60 * 60


class RiotServiceError(Exception):
    """Fallo al hablar con Riot. `retryable` indica si merece la pena insistir."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@dataclass(slots=True)
class FailedMatch:
    game_id: str
    reason: str
    retryable: bool


@dataclass(slots=True)
class _CachedPuuid:
    value: dict[str, str]
    expires_at: float


_puuid_cache: dict[str, _CachedPuuid] = {}


def _classify(err: ApiError) -> RiotServiceError:
    """Traduce un error HTTP de Riot a algo que la API pueda comunicar con sentido."""
    status = getattr(err.response, "status_code", None)
    if status == 403:
        return RiotServiceError(
            "API Key inválida o caducada. Las dev keys de Riot expiran cada 24h.",
            status=403, retryable=False,
        )
    if status == 404:
        return RiotServiceError("Recurso no encontrado en Riot.", status=404, retryable=False)
    if status == 429:
        return RiotServiceError("Rate limit de Riot excedido.", status=429, retryable=True)
    if status is not None and status >= 500:
        return RiotServiceError(f"Riot devolvió {status} (fallo temporal suyo).",
                                status=status, retryable=True)
    return RiotServiceError(f"Error de API de Riot: {status}", status=status, retryable=False)


def _retry_after(err: ApiError, attempt: int) -> float:
    """Segundos a esperar: la cabecera Retry-After de Riot si existe, si no backoff exponencial.
    Siempre acotada por MAX_RETRY_AFTER_SECONDS."""
    headers = getattr(err.response, "headers", {}) or {}
    raw = headers.get("Retry-After")
    delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
    if raw:
        try:
            delay = float(raw)
        except (TypeError, ValueError):
            pass
    return min(delay, MAX_RETRY_AFTER_SECONDS)


# ─────────────────────────── baselines de rating por rol ────────────────────────────
#
# El rating es 100% objetivo (decisión 2026-08-21: sin modificadores de disciplina), pero
# "objetivo" no significa "ignorar el rol": un soporte con 1.2 CS/min NO es peor que un
# ADC con 8. Cada rol define qué considera Riot una partida "normal" y el rating mide la
# partida contra esa normalidad.

@dataclass(slots=True, frozen=True)
class _RoleProfile:
    cs_target: float
    kp_target: float
    dpm_target: float
    # Soporte y jungla viven del impacto en equipo, no del farmeo: su KP pesa más.
    kp_slope: float = 20.0
    kp_cap: float = 10.0
    # Visión por minuto; None = el rol no puntúa visión (lanes).
    vision_target: float | None = None
    vision_slope: float = 10.0
    vision_cap: float = 10.0


_ROLE_PROFILES: dict[str, _RoleProfile] = {
    "TOP": _RoleProfile(cs_target=7.5, kp_target=0.55, dpm_target=600),
    "MIDDLE": _RoleProfile(cs_target=7.5, kp_target=0.60, dpm_target=650),
    "BOTTOM": _RoleProfile(cs_target=7.5, kp_target=0.65, dpm_target=600),
    "JUNGLE": _RoleProfile(
        cs_target=5.75, kp_target=0.70, dpm_target=500,
        kp_slope=30.0, kp_cap=15.0,
        vision_target=0.5, vision_slope=5.0, vision_cap=5.0,
    ),
    "UTILITY": _RoleProfile(
        cs_target=1.25, kp_target=0.70, dpm_target=250,
        kp_slope=30.0, kp_cap=15.0,
        vision_target=1.0,
    ),
}
# ARAM, remakes, posiciones sin asignar: perfil neutro heredado de la fórmula original.
_DEFAULT_PROFILE = _RoleProfile(cs_target=7.0, kp_target=0.50, dpm_target=550)


class RiotService:
    def __init__(self, settings: Settings):
        self._settings = settings
        # riotwatcher trae un BasicRateLimiter por defecto que lee las cabeceras X-Rate-Limit y
        # duerme proactivamente; su limitador de aplicación es atributo de clase, así que el
        # estado se comparte entre ambos watchers y entre instancias del proceso.
        self._lol = LolWatcher(settings.riot_api_key)
        self._riot = RiotWatcher(settings.riot_api_key)
        self._route = settings.continental_route
        # Summoner-V4 y League-V4 se enrutan por PLATAFORMA (EUW1...), no por continente.
        self._platform = settings.riot_region

    # ------------------------------------------------------------------ reintentos

    async def _call_with_retry(
        self, description: str, fn: Callable[..., Any], /, *args: Any
    ) -> Any:
        """Llamada síncrona a Riot en el threadpool, con reintentos ante errores temporales.

        Antes sólo el fetch de partidas reintentaba: un 429 en la resolución del PUUID o en
        el listado de match ids mataba el sync entero a la primera. Aquí pasa TODO.
        """
        last: RiotServiceError | None = None
        for attempt in range(MAX_RETRIES):
            try:
                return await run_in_threadpool(fn, *args)
            except ApiError as err:
                last = _classify(err)
                if not last.retryable or attempt == MAX_RETRIES - 1:
                    raise last from err
                delay = _retry_after(err, attempt)
                log.info("Reintentando %s en %.1fs (intento %d/%d)",
                         description, delay, attempt + 1, MAX_RETRIES)
                await asyncio.sleep(delay)
        raise last or RiotServiceError(f"No se pudo completar la llamada a Riot ({description})")

    # ------------------------------------------------------------------ cuentas

    async def resolve_account(self, riot_id: str) -> dict[str, str]:
        """Riot ID 'Nombre#TAG' -> {puuid, name, tag}. Cacheado 24h."""
        if "#" not in riot_id:
            raise RiotServiceError("El formato debe ser Nombre#Tag (ej: Faker#KR1)", retryable=False)

        game_name, tag_line = (part.strip() for part in riot_id.split("#", 1))
        if not game_name or not tag_line:
            raise RiotServiceError("Nombre o Tag vacíos. Usa Nombre#Tag.", retryable=False)

        key = f"{self._route}:{game_name.lower()}#{tag_line.lower()}"
        now = asyncio.get_running_loop().time()
        cached = _puuid_cache.get(key)
        if cached and cached.expires_at > now:
            return cached.value

        account = await self._call_with_retry(
            f"cuenta {game_name}#{tag_line}",
            self._riot.account.by_riot_id,
            self._route, game_name, tag_line,
        )

        resolved = {
            "puuid": account["puuid"],
            "name": account["gameName"],
            "tag": account["tagLine"],
        }
        _puuid_cache[key] = _CachedPuuid(resolved, now + PUUID_CACHE_TTL_SECONDS)
        return resolved

    # ------------------------------------------------------------------ ladder (League-V4)

    async def fetch_ranked_solo_entry(self, riot_id: str) -> dict[str, Any] | None:
        """LP actual de Ranked Solo/Duo: {lp, tier, division, wins, losses}.

        None si el invocador no está clasificado en esa cola. Necesita una parada intermedia
        en Summoner-V4: League-V4 indexa por summonerId encriptado, no por PUUID (el PUUID
        ya viene cacheado de resolve_account, así que el coste extra real son 2 llamadas).

        Riot no expone el LP ganado/perdido por partida desde que retiraron ese dato del
        match detail: este snapshot es la única fuente honesta para alimentar la gráfica.
        """
        account = await self.resolve_account(riot_id)
        puuid = account["puuid"]

        summoner = await self._call_with_retry(
            f"invocador {account['name']}#{account['tag']}",
            self._lol.summoner.by_puuid,
            self._platform, puuid,
        )
        entries = await self._call_with_retry(
            f"liga de {account['name']}#{account['tag']}",
            self._lol.league.by_summoner,
            self._platform, summoner["id"],
        )

        for entry in entries:
            if entry.get("queueType") == "RANKED_SOLO_5x5":
                return {
                    "lp": int(entry["leaguePoints"]),
                    "tier": entry.get("tier"),
                    "division": entry.get("rank"),
                    "wins": int(entry.get("wins", 0)),
                    "losses": int(entry.get("losses", 0)),
                }
        log.info("%s sin clasificación en Solo/Duo", riot_id)
        return None

    # ------------------------------------------------------------------ partidas

    async def fetch_recent_matches(
        self, riot_id: str, limit: int = 10, queue: int | None = 420
    ) -> tuple[list[dict[str, Any]], list[FailedMatch]]:
        """Descarga partidas recientes. Devuelve (partidas_ok, fallos) — los fallos NO se ocultan."""
        account = await self.resolve_account(riot_id)
        puuid = account["puuid"]

        match_ids: list[str] = await self._call_with_retry(
            "listado de partidas",
            partial(
                self._lol.match.matchlist_by_puuid,
                self._route, puuid, count=min(limit, 100), queue=queue,
            ),
        )

        matches: list[dict[str, Any]] = []
        failures: list[FailedMatch] = []

        for match_id in match_ids:
            try:
                raw = await self._fetch_match_with_retry(match_id)
            except RiotServiceError as exc:
                log.warning("Partida %s no descargada: %s", match_id, exc)
                failures.append(FailedMatch(match_id, str(exc), exc.retryable))
                continue

            parsed = self._parse(raw, puuid)
            if parsed is None:
                # El jugador no aparece entre los participantes: dato inconsistente de Riot.
                failures.append(FailedMatch(match_id, "El jugador no figura en la partida", False))
                continue
            matches.append(parsed)

        return matches, failures

    async def _fetch_match_with_retry(self, match_id: str) -> dict[str, Any]:
        return await self._call_with_retry(
            f"partida {match_id}", self._lol.match.by_id, self._route, match_id
        )

    def _parse(self, raw: dict[str, Any], puuid: str) -> dict[str, Any] | None:
        """Aplana una partida de Match-V5 a las columnas de la tabla `matches`."""
        info = raw["info"]
        me = next((p for p in info["participants"] if p["puuid"] == puuid), None)
        if me is None:
            return None

        role = me.get("teamPosition") or ""
        if not role or role == "Invalid":
            role = me.get("individualPosition") or "Unknown"

        duration_min = round(info["gameDuration"] / 60, 2)
        cs_total = me["totalMinionsKilled"] + me["neutralMinionsKilled"]

        participants = self._extract_participants(info["participants"], duration_min)

        return {
            "game_id": raw["metadata"]["matchId"],
            # UTC explícito: la interpretación a hora local se hace al consultar el heatmap.
            "date": datetime.fromtimestamp(info["gameEndTimestamp"] / 1000, tz=UTC),
            "champion": me["championName"],
            "role": role,
            "kills": me["kills"],
            "deaths": me["deaths"],
            "assists": me["assists"],
            "cs_total": cs_total,
            "cs_min": round(cs_total / duration_min, 2) if duration_min > 0 else 0.0,
            "control_wards": me["visionWardsBoughtInGame"],
            "win": bool(me["win"]),
            "enemy_champion": self._enemy_laner(info, me),
            "game_duration_minutes": duration_min,
            "queue_id": info.get("queueId"),
            "participants": participants,
        }

    @staticmethod
    def calculate_participant_rating(participant_data: dict[str, Any], match_duration: float) -> float:
        """Rating universal 0-100 con expectativas por rol (`_ROLE_PROFILES`).

        100% objetivo (decisión 2026-08-21: sin modificadores de disciplina); los roles no
        alteran la filosofía, sólo qué se considera "normal". Componentes:

          * base 50, ±15 por victoria/derrota;
          * KDA: hasta +20 y hasta -10 (con deaths=0 el KDA es kills+assists);
          * CS/min contra el target del rol (lanes 7.5, jungla 5.75, soporte 1.25): ±10;
          * KP% contra el target del rol; soporte y jungla pesan más (±15 vs ±10);
          * DPM contra el target del rol (mid 650, lanes 600, jungla 500, soporte 250): ±10;
          * visión/minuto donde importa: soporte target 1.0 (±10), jungla 0.5 (±5);
          * muertes por encima de 3: penalización adicional de hasta -15.

        Posición desconocida -> perfil neutro. Resultado clampado a [0, 100], 1 decimal.
        """
        duration_min = max(float(match_duration), 1.0)
        kills = int(participant_data.get("kills", 0))
        deaths = int(participant_data.get("deaths", 0))
        assists = int(participant_data.get("assists", 0))
        cs = int(participant_data.get("cs", 0))
        kp = float(participant_data.get("kill_participation", 0.0))
        damage = int(participant_data.get("total_damage", 0))
        vision_score = int(participant_data.get("vision_score", 0))

        position = str(participant_data.get("team_position") or "").upper()
        profile = _ROLE_PROFILES.get(position, _DEFAULT_PROFILE)

        kda = (kills + assists) / deaths if deaths > 0 else float(kills + assists)
        cs_per_min = cs / duration_min
        dpm = damage / duration_min

        score = 50.0
        score += 15.0 if participant_data.get("win") else -15.0
        score += max(-10.0, min(20.0, (kda - 2.0) * 5.0))
        score += max(-10.0, min(10.0, (cs_per_min - profile.cs_target) * 3.0))
        score += max(-profile.kp_cap, min(profile.kp_cap, (kp - profile.kp_target) * profile.kp_slope))
        score += max(-10.0, min(10.0, (dpm - profile.dpm_target) / 50.0))
        if profile.vision_target is not None:
            vision_per_min = vision_score / duration_min
            score += max(
                -profile.vision_cap,
                min(profile.vision_cap, (vision_per_min - profile.vision_target) * profile.vision_slope),
            )
        score -= min(15.0, max(0.0, deaths - 3) * 5.0)
        return round(max(0.0, min(100.0, score)), 1)

    @staticmethod
    def _extract_participants(
        raw_participants: list[dict[str, Any]], match_duration_minutes: float
    ) -> list[dict[str, Any]]:
        """Extrae los 10 participantes: Riot ID, KDA, CS, items (7 slots, incluido trinket),
        hechizos, daño y rating universal calculado en backend."""
        # La KP necesita los kills totales de cada equipo: primera pasada de agregación.
        team_kills: dict[int, int] = {}
        for p in raw_participants:
            tid = p.get("teamId", 0)
            team_kills[tid] = team_kills.get(tid, 0) + p.get("kills", 0)

        result: list[dict[str, Any]] = []
        for p in raw_participants:
            cs = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
            team_id = p.get("teamId", 0)

            game_name = p.get("riotIdGameName") or ""
            tag_line = p.get("riotIdTagline") or ""
            if game_name and tag_line:
                player_name = f"{game_name}#{tag_line}"
            else:
                # Partidas muy antiguas o bots sin Riot ID: caemos al summonerName clásico.
                player_name = p.get("summonerName") or "Unknown"

            participant: dict[str, Any] = {
                "champion_name": p.get("championName", "Unknown"),
                "puuid": p.get("puuid", ""),
                "player_name": player_name,
                "kills": p.get("kills", 0),
                "deaths": p.get("deaths", 0),
                "assists": p.get("assists", 0),
                "cs": cs,
                "items": [
                    p.get("item0", 0), p.get("item1", 0), p.get("item2", 0),
                    p.get("item3", 0), p.get("item4", 0), p.get("item5", 0),
                    p.get("item6", 0),  # trinket
                ],
                "summoner_spells": [
                    p.get("summoner1Id", 0),
                    p.get("summoner2Id", 0),
                ],
                "team_id": team_id,
                "team_position": p.get("teamPosition", p.get("individualPosition", "Unknown")),
                "win": bool(p.get("win", False)),
                "total_damage": p.get("totalDamageDealtToChampions", 0),
                "total_damage_taken": p.get("totalDamageTaken", 0),
                "gold_earned": p.get("goldEarned", 0),
                "vision_score": p.get("visionScore", 0),
            }

            total_team_kills = team_kills.get(team_id, 0)
            participant["kill_participation"] = (
                round((participant["kills"] + participant["assists"]) / total_team_kills, 3)
                if total_team_kills > 0 else 0.0
            )
            participant["rating"] = RiotService.calculate_participant_rating(
                participant, match_duration_minutes
            )
            # Estampado de trazabilidad: qué fórmula generó el rating de arriba.
            participant["rating_version"] = RATING_VERSION
            result.append(participant)
        return result

    @staticmethod
    def _enemy_laner(info: dict[str, Any], me: dict[str, Any]) -> str:
        """Rival directo = mismo `teamPosition`, equipo contrario. 'Unknown' en remakes y
        partidas sin rol asignado (valor que `nemesis()` filtra explícitamente)."""
        role = me.get("teamPosition")
        if not role or role == "Invalid":
            return "Unknown"
        for p in info["participants"]:
            if p["teamId"] != me["teamId"] and p.get("teamPosition") == role:
                return p["championName"]
        return "Unknown"
