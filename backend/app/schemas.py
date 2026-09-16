"""Esquemas Pydantic — el contrato de la API.

Nota de diseño: el monolito devolvía la KDA como string ya formateado ("5.0 / 2.0 / 10.0") y la UI
lo re-parseaba con `.split('/')`, que es exactamente donde vivía el bug de `app.py:128`. Aquí la API
devuelve **números**; formatear es responsabilidad del frontend.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.config import ROUTING_MAP

# Valores canónicos de `impact_rating`. Se exponen en /api/config para que el frontend no los
# duplique (en Streamlit estaban hardcodeados dos veces, y las dos listas podían divergir).
IMPACT_RATINGS = (
    "Carree (1v9)",
    "Hice mi trabajo",
    "Fui Carreado",
    "Invisible",
    "Inteé (Perdí la lane)",
)

# Trazabilidad del rating: qué versión de `calculate_participant_rating` (services/riot.py)
# generó la puntuación guardada en el JSONB. v1 = fórmula con perfiles por rol
# (`_ROLE_PROFILES`, decisión 2026-08-21). Si la matemática cambia, se sube este número y
# backend/scripts/rescore_participants.py re-etiqueta las filas antiguas.
RATING_VERSION = 1


class Participant(BaseModel):
    """Un jugador dentro de una partida (10 por match).

    `player_name` sustituye al viejo `summoner_name` (que Riot ya no rellena en Match-V5): ahora
    se guarda el Riot ID completo "GameName#TAG". Los campos con default toleran filas antiguas
    del JSONB sincronizadas antes del nuevo esquema, para que /api/matches no reviente; tras un
    TRUNCATE + resync todos los participantes salen completos.
    """
    champion_name: str
    puuid: str = ""
    player_name: str = Field(default="", description="Riot ID completo 'GameName#TAG'")
    kills: int
    deaths: int
    assists: int
    cs: int
    items: list[int] = Field(
        default_factory=list,
        description="7 IDs de items: item0-item5 + trinket en item6 (0 = slot vacío)",
    )
    summoner_spells: list[int] = Field(default_factory=list, description="2 IDs de hechizos")
    team_id: int
    team_position: str
    win: bool
    total_damage: int = Field(default=0, description="totalDamageDealtToChampions de Riot")
    total_damage_taken: int = 0
    gold_earned: int = 0
    vision_score: int = 0
    kill_participation: float = Field(default=0.0, ge=0.0, le=1.0)
    rating: float = Field(default=0.0, ge=0.0, le=100.0, description="Rating universal 0-100")
    rating_version: int = Field(
        default=RATING_VERSION,
        ge=1,
        description="Versión de la fórmula que generó `rating` (trazabilidad)",
    )
    # Triángulo del Laning: diffs del usuario contra su rival directo al minuto 15
    # (extraídos del Timeline de Riot en el sync). NULL/ausente en partidas sin datos.
    gd15: float | None = Field(default=None, description="Diferencia de oro a los 15:00 (a tu favor si >0)")
    xpd15: float | None = Field(default=None, description="Diferencia de XP a los 15:00")
    csd15: float | None = Field(default=None, description="Diferencia de CS (minions+jungle) a los 15:00")
    # Línea base del rol calculada en LECTURA (services/baselines.py, nunca se persiste):
    # lo "esperable" de CS/min, DPM, KP% y visión total para comparar en la UI de Full Stats.
    expected_stats: ParticipantExpectedStats | None = Field(
        default=None,
        description="Valores esperados de este rol para la duración de la partida",
    )


class ParticipantExpectedStats(BaseModel):
    """Valores esperados de un rol para una partida concreta (baselines, no persistidos)."""

    cs_per_min: float
    dpm: float
    kill_participation: float = Field(ge=0.0, le=1.0, description="Ratio 0-1")
    vision_score: float = Field(description="Visión total esperada = visión/min × duración real")


class Match(BaseModel):
    """Una partida. Los campos objetivos vienen de Riot; los subjetivos los rellena el usuario."""

    # Objetivos (escritos una vez por el sync)
    game_id: str
    date: datetime
    champion: str
    role: str
    kills: int
    deaths: int
    assists: int
    cs_total: int
    cs_min: float
    control_wards: int
    win: bool
    enemy_champion: str | None = None
    game_duration_minutes: float | None = None
    queue_id: int | None = None
    participants: list[Participant] | None = None

    # Subjetivos (nullable: una partida sincronizada pero no revisada los tiene todos vacíos)
    lp_change: int | None = None
    tilt_level: int | None = None
    impact_rating: str | None = None
    notes: str | None = None
    vod_review: bool = False


class MatchUpdate(BaseModel):
    """Actualización parcial de los campos subjetivos.

    Ojo: en el monolito, `update_match_details` se saltaba los `None`, así que era imposible
    devolver un campo a NULL. Aquí se distingue "no enviado" (ausente del JSON) de "enviado como
    null" usando `model_fields_set`, así que sí se puede borrar un valor mal introducido.
    """

    lp_change: int | None = None
    tilt_level: int | None = Field(default=None, ge=1, le=5)
    impact_rating: str | None = None
    notes: str | None = None
    vod_review: bool | None = None

    def changes(self) -> dict[str, object]:
        """Solo los campos presentes en el payload original."""
        return {k: getattr(self, k) for k in self.model_fields_set}


# ─────────────────────────────── Escout del rival ───────────────────────────────

# Las maestrías vienen como `championId` numérico de Data Dragon ("103" = Ahri); el nombre
# visible se resuelve contra el índice de campeones (`services/datadragon.py`, campo `key`).


class ScoutMasteryChampion(BaseModel):
    champion: str = Field(description="Nombre visible del campeón ('Lee Sin')")
    champion_key: str = Field(description="Id numérico de Data Dragon ('103')")
    mastery_level: int = Field(ge=0, description="Nivel de maestría (sin tope: Riot eliminó el cap de 7 en 2026)")
    points: int = Field(ge=0, description="Puntos de maestría acumulados")


class ScoutOpponent(BaseModel):
    """Escout de un rival de línea concreto: sus 3 campeones más jugados vía Champion Mastery.

    `opponent_champion` es lo que jugó contra ti en la partida escouteada; `top_champions`
    son sus maestrías más altas (ordenadas por puntos). `cached` dice si la respuesta vino de
    la caché en DB (`scout_cache`, TTL 24h) o de una llamada fresca a Riot — el front lo usa
    para no alarmarse si la llamada tarda.

    `note` explica por qué no hay datos cuando los hay (rival sin maestrías, puuid ausente,
    rol sin asignar...), para que la UI muestre un mensaje útil en vez de un hueco.
    """

    game_id: str
    opponent_puuid: str
    opponent_name: str = ""
    opponent_champion: str = ""
    opponent_role: str = ""
    top_champions: list[ScoutMasteryChampion] = Field(default_factory=list)
    cached: bool = False
    cached_at: datetime | None = None
    note: str = ""


# ─────────────────────────────── Veredicto del meta ───────────────────────────────

# Regla de negocio: "históricamente favorable" es winrate previo >= 55 y "se volvió
# negativo" es <50% en el parche actual (constantes reales en repositories/stats.py).


class MetaVerdict(BaseModel):
    """Winrate de un enfrentamiento (tu campeón vs enemigo) separado por parche.

    `games_*_current` = partidas de la `game_version` del parche actual; `games_previous` =
    todo el historial de parches anteriores (incluidas las filas legacy con versión NULL).
    `meta_shift` marca exactamente el caso que alarma al usuario: un cruce que era favorable
    y ahora está por debajo del 50% — la alerta de "el meta te ha pasado por encima".
    """

    user_champion: str
    enemy_champion: str
    games_current: int
    wins_current: int
    winrate_current: float | None = Field(default=None, description="NULL sin partidas en el parche actual")
    games_previous: int
    wins_previous: int
    winrate_previous: float | None = Field(default=None, description="NULL sin historial previo")
    delta_pp: float | None = Field(default=None, description="winrate (parche actual) - winrate (anterior), en puntos")
    meta_shift: bool = Field(default=False, description="Favorable antes, negativo ahora, con muestra mínima")


class MetaVerdictResponse(BaseModel):
    current_patch: str = Field(description="Parche de Riot normalizado a 'X.Y' con el que se separaron los datos")
    verdicts: list[MetaVerdict]


class ChampionStats(BaseModel):
    """Incluye `winrate` y `kda_ratio`, que la query original nunca devolvía pese a que la
    Tab 3 las pedía -> KeyError permanente. Ahora se calculan en SQL."""

    champion: str
    games_played: int
    wins: int
    winrate: float
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    kda_ratio: float
    avg_cs_min: float
    avg_dpm: float = 0


class ChampionRoleSummary(BaseModel):
    """Winrate/KDA del usuario por (campeón, rol, cola).

    Con `HAVING COUNT(*) >= 3` en SQL: con menos partidas el winrate es puro ruido y la
    tabla no puede separar "rindo bien" de "he tenido suerte dos veces". El rol es la
    columna `matches.role` (el teamPosition que Riot reportó en la partida), no el
    `team_position` del JSONB: aquí importa cómo llegó la fila, una fila = una partida.
    """

    champion: str
    role: str
    queue_id: int
    games_played: int
    wins: int
    losses: int
    winrate: float
    kda_ratio: float


class SessionBlock(BaseModel):
    """Un bloque de partidas consecutivas (las 5 más recientes o las 5 anteriores)."""

    games: int
    wins: int
    losses: int
    winrate: float
    avg_kda: float


class SessionFatigue(BaseModel):
    """Diagnóstico de fatiga de sesión comparando dos bloques de 5 partidas.

    Las 10 partidas válidas más recientes se parten en dos bloques: `recent` (las 5 más
    nuevas) vs `previous` (las 5 que las preceden). `sample_ok` exige ambas ventanas
    completas — con menos de 6 partidas no hay bloque anterior y nada que comparar.

    `fatigue_detected` (autopilot) se activa con una caída severa de winrate (>=20pp) o un
    desplome de KDA (>=2.0) entre bloques; los umbrales viven en `repositories/stats.py`
    porque son reglas de negocio, no de contrato. `message` da contexto en español con
    números reales, no un veredicto seco.
    """

    previous: SessionBlock | None = None
    recent: SessionBlock | None = None
    sample_ok: bool = False
    winrate_delta_pp: float | None = None
    kda_delta: float | None = None
    fatigue_detected: bool = False
    message: str = ""


class HeatmapCell(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0 = Domingo, 1 = Lunes ... 6 = Sábado")
    time_block: str = Field(description="Madrugada | Mañana | Tarde | Noche")
    games_played: int
    wins: int
    losses: int
    winrate: float


class HeatmapResponse(BaseModel):
    """Wrapper del heatmap: celdas + mejor/peor horario (con umbral mínimo de 3 partidas)."""

    cells: list[HeatmapCell]
    best_slot: HeatmapCell | None = None
    worst_slot: HeatmapCell | None = None


class TrendPoint(BaseModel):
    """Un punto de la serie temporal de KPIs de mejora (últimas N partidas válidas).

    Orden cronológico ascendente (partida más antigua primero) para que las gráficas de
    línea recorran el tiempo de izquierda a derecha. `timestamp` es la hora de juego en UTC.

    `vision_delta` y `kp` se leen del JSONB `participants` (nulos en filas legacy o cuando
    no existe rival directo); `win` es el resultado de la partida, siempre presente.
    """

    game_id: str
    timestamp: datetime
    cs_min: float
    dpm: float
    kda: float
    vision_delta: float | None = None
    kp: float | None = None
    win: bool


class LaningSummary(BaseModel):
    """Promedios del Triángulo del Laning sobre las últimas partidas con datos de Timeline.

    `games_analyzed` = cuántas partidas (de la ventana) alimentaron el promedio; 0 cuando los
    datos de timeline aún no se han sincronizado. Los promedios son None sin ninguna partida.
    """

    avg_gd15: float | None = Field(default=None, description="Diferencia media de oro a los 15:00 (a tu favor si >0)")
    avg_xpd15: float | None = Field(default=None, description="Diferencia media de XP a los 15:00")
    avg_csd15: float | None = Field(default=None, description="Diferencia media de CS a los 15:00")
    games_analyzed: int = Field(
        default=0,
        description="Partidas con datos de timeline en la ventana (mínimo piramidal del triángulo)",
    )


class PatchChampionInfo(BaseModel):
    """Rendimiento de un campeón del pool en el parche actual vs. los anteriores."""

    champion: str
    games_current: int
    wins_current: int
    winrate_current: float | None = Field(default=None, description="NULL si no hay partidas en el parche actual")
    games_previous: int
    wins_previous: int
    winrate_previous: float | None = Field(default=None, description="NULL si el campeón nunca se jugó antes")
    delta_pp: float | None = Field(default=None, description="winrate actual - winrate previo, en puntos porcentuales")
    dropped: bool = Field(default=False, description="Caída >4pp con mínimo de 5 partidas en el parche actual")


class PatchAlert(BaseModel):
    """Alerta de parche: siempre devuelve datos; el frontend decide si mostrar banner según
    `has_current_games` (parche demasiado nuevo = sin partidas aún) y `alerting_champions`."""

    current_patch: str
    has_current_games: bool
    alerting_champions: list[str] = Field(default_factory=list)
    champions: list[PatchChampionInfo]


class WeeklyTopChampion(BaseModel):
    """Campeón más jugado de la semana (nombre visible; el avatar lo resuelve el frontend vía Data Dragon)."""

    champion: str
    games: int
    wins: int


class WeeklyBestMatch(BaseModel):
    """La mejor partida de la semana, según el rating 0-100 del usuario."""

    game_id: str
    date: datetime
    champion: str
    kills: int
    deaths: int
    assists: int
    kda: float
    rating: float


class WeeklyReport(BaseModel):
    """Resumen de los últimos 7 días (ventana según fecha UTC) para el Reporte Semanal."""

    period_start: date
    period_end: date
    total_games: int
    wins: int
    losses: int
    winrate: float = 0.0
    avg_kda: float = 0.0
    most_played: WeeklyTopChampion | None = None
    best_match: WeeklyBestMatch | None = None


class MatchupStats(BaseModel):
    """Estadísticas históricas del cruce de dos campeones (Tú contra enemigo)."""

    user_champion: str
    enemy_champion: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    winrate: float = 0.0
    avg_kills: float = 0.0
    avg_deaths: float = 0.0
    avg_assists: float = 0.0
    kda_ratio: float = 0.0


class MatchupNotes(BaseModel):
    """Notas persistidas para un emparejamiento concreto."""

    user_champion: str
    enemy_champion: str
    notes: str = ""
    updated_at: datetime | None = None


class MatchupNotesUpdate(BaseModel):
    """Payload del PUT: reemplazo completo de las notas del cruce."""

    notes: str = ""


class SyncError(BaseModel):
    game_id: str
    reason: str
    retryable: bool


class LpCapture(BaseModel):
    """LP de Solo/Duo capturado automáticamente al cerrar el sync (League-V4).

    `delta_assigned` es el LP neto escrito como `lp_change` en la partida más reciente sin
    review manual; None cuando no había snapshot previo (línea base), delta 0, o ninguna
    partida candidata. Nunca sobrescribe una review del usuario.
    """

    lp: int
    tier: str | None = None
    division: str | None = None
    delta_assigned: int | None = None


class SyncResult(BaseModel):
    """El sync ya no miente. El monolito decía "✨ Todo actualizado" incluso cuando un 429 había
    descartado partidas en silencio; ahora los fallos viajan en la respuesta."""

    fetched: int
    inserted: int
    skipped: int
    errors: list[SyncError] = []
    lp_captured: LpCapture | None = None
    losing_streak_warning: bool = Field(
        default=False,
        description="True si las últimas 3+ partidas son derrotas consecutivas (Tilt Alert)",
    )
    degraded_api: bool = Field(
        default=False,
        description="True si Riot se degradó a mitad del sync: se guardó el progreso parcial "
        "pero no se pudo completar. Reintenta con otro POST (insert_many es idempotente).",
    )


class SyncAccepted(BaseModel):
    """Respuesta inmediata del POST /api/sync: el trabajo pesado corre en BackgroundTasks."""

    status: Literal["processing"]
    message: str


class SyncStatus(BaseModel):
    """Estado del sync en curso (o del último terminado), para el polling del frontend.

    `partial` = terminó con Riot degradado: `result.degraded_api` es True y lo descargado
    hasta entonces quedó guardado."""

    status: Literal["idle", "processing", "success", "partial", "error"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: SyncResult | None = None
    error: str | None = None


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    riot_key_present: bool
    warnings: list[str] = []


# ─────────────────────────────── configuración ────────────────────────────────

# "Champion Pool (Max 3)" es una regla de La Constitución, no una sugerencia: la premisa del
# proyecto es forzar consistencia. Se valida en la API y también con un CHECK en la tabla.
CHAMPION_POOL_MAX = 3


class UserSettings(BaseModel):
    """Config completa del frontend: valores canónicos + configuración persistida del usuario.

    GET /api/config devuelve todo junto para que el frontend no necesite múltiples llamadas.
    Los campos canónicos (impact_ratings, regions, etc.) son de solo lectura; los campos
    editables (champion_pool, target_cs_min, max_deaths) se actualizan con PUT.
    """

    # Persistidos (editables vía PUT)
    champion_pool: list[str]
    target_cs_min: float
    max_deaths: float
    target_dpm: int = Field(default=500, ge=0, le=3000, description="Meta de DPM (Daño Por Minuto)")
    target_kp_percent: int = Field(default=50, ge=0, le=100, description="Meta de Kill Participation en %")
    target_vision_score: int = Field(default=20, ge=0, le=200, description="Meta de Vision Score por partida")
    updated_at: datetime | None = None

    # Canónicos (solo lectura, no persistidos en DB)
    impact_ratings: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    champion_pool_max: int = CHAMPION_POOL_MAX
    display_timezone: str = "Europe/Madrid"
    # Vinculación Riot del usuario (migración 014): persistida en user_settings, no en el .env.
    riot_id: str = ""
    riot_region: str = "EUW1"


class UserSettingsUpdate(BaseModel):
    """Reemplazo completo de la configuración (semántica de PUT)."""

    champion_pool: list[str] = Field(
        max_length=CHAMPION_POOL_MAX,
        description=f"Máximo {CHAMPION_POOL_MAX} campeones (regla de La Constitución)",
    )
    target_cs_min: float = Field(gt=0, le=20, description="Meta de CS por minuto")
    max_deaths: float = Field(gt=0, le=20, description="Tope de muertes por partida")
    target_dpm: int = Field(default=500, ge=0, le=3000, description="Meta de DPM")
    target_kp_percent: int = Field(default=50, ge=0, le=100, description="Meta de Kill Participation en %")
    target_vision_score: int = Field(default=20, ge=0, le=200, description="Meta de Vision Score")

    @field_validator("champion_pool")
    @classmethod
    def _clean_pool(cls, pool: list[str]) -> list[str]:
        """Normaliza el pool: quita blancos y duplicados (insensible a mayúsculas).

        Se hace en el servidor a propósito. En Streamlit el pool venía de un `split(',')` sobre
        texto libre, así que "Jax, , jax" producía entradas vacías y duplicadas que rompían la
        comprobación de "fuera de pool".
        """
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in pool:
            champion = raw.strip()
            if not champion or champion.lower() in seen:
                continue
            seen.add(champion.lower())
            cleaned.append(champion)
        return cleaned


class RiotLinkRequest(BaseModel):
    """Cuerpo de PUT /api/settings/riot: vincula la cuenta Riot del usuario.

    El Riot ID es el `GameName#TAG` que Riot usa para resolver el PUUID en el sync. La
    validación (formato + región conocida) vive en el servidor: el onboarding de la v2.1
    sólo envía `{riot_id, region}` y no valida nada por su cuenta.
    """

    riot_id: str = Field(min_length=1, description="Riot ID, formato 'Nombre#TAG'")
    region: str = Field(default="EUW1", description="Región de plataforma (ROUTING_MAP)")

    @field_validator("riot_id")
    @classmethod
    def _validate_riot_id(cls, value: str) -> str:
        stripped = value.strip()
        if "#" not in stripped:
            raise ValueError("Formato inválido, usa 'Nombre#TAG'")
        game_name, tag_line = (part.strip() for part in stripped.split("#", 1))
        if not game_name or not tag_line:
            raise ValueError("GameName y TAG no pueden estar vacíos")
        return stripped

    @field_validator("region")
    @classmethod
    def _validate_region(cls, value: str) -> str:
        region = value.strip().upper()
        if region not in ROUTING_MAP:
            raise ValueError(
                f"Región desconocida: {value!r}. Válidas: {', '.join(sorted(ROUTING_MAP))}"
            )
        return region


# ───────────────────────────── metadatos (Data Dragon) ────────────────────────────

# Diccionarios "limpios": el JSON crudo de Data Dragon ronda 1-8 MB con stats, tags y HTML;
# aquí viajan sólo los campos que la UI pinta. Las claves son las mismas que usa Riot:
# campeones por id de Data Dragon ("LeeSin"), items y hechizos por id numérico ("3078", "4").


class ChampionMeta(BaseModel):
    id: str = Field(description="Id de Data Dragon ('LeeSin'), clave del dict")
    key: str = Field(default="", description="Id numérico de Data Dragon ('103'), el de Champion Mastery-V4")
    name: str = Field(description="Nombre visible ('Lee Sin') — así se guarda en matches.champion")
    title: str = ""
    description: str = ""
    image: str = Field(description="URL absoluta del cuadrado en Data Dragon")


class ItemMeta(BaseModel):
    id: int
    name: str
    description: str = Field(default="", description="Descripción sin etiquetas HTML")
    image: str


class SpellMeta(BaseModel):
    id: int = Field(description="Id numérico del hechizo en el API de partida (4 = Flash)")
    name: str
    description: str = ""
    image: str


class ChampionsIndex(BaseModel):
    patch: str
    champions: dict[str, ChampionMeta]


class ItemsIndex(BaseModel):
    patch: str
    items: dict[str, ItemMeta]


class SpellsIndex(BaseModel):
    patch: str
    spells: dict[str, SpellMeta]


# ───────────────────────────── observabilidad ────────────────────────────

# Latencias en memoria por (método, plantilla de ruta). Nivel mínimo a propósito: detectar
# "Supabase está lento hoy" sin Prometheus ni APM externo. Mono-proceso, igual que _SyncState.


class EndpointMetric(BaseModel):
    method: str
    path: str = Field(description="Plantilla de ruta ('/api/matches/{game_id}'), no el path literal")
    count: int
    errors: int = Field(description="Peticiones terminadas en 5xx o excepción")
    p50_ms: float
    p95_ms: float
    max_ms: float


class MetricsSnapshot(BaseModel):
    uptime_seconds: int
    endpoints: list[EndpointMetric]
