"""Esquemas Pydantic — el contrato de la API.

Nota de diseño: el monolito devolvía la KDA como string ya formateado ("5.0 / 2.0 / 10.0") y la UI
lo re-parseaba con `.split('/')`, que es exactamente donde vivía el bug de `app.py:128`. Aquí la API
devuelve **números**; formatear es responsabilidad del frontend.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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


class StatsSummary(BaseModel):
    total_games: int
    total_wins: int
    winrate: float
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    kda_ratio: float
    avg_cs_min: float


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


class HeatmapCell(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0 = Domingo, 1 = Lunes ... 6 = Sábado")
    time_block: str = Field(description="Madrugada | Mañana | Tarde | Noche")
    games_played: int
    wins: int
    losses: int
    winrate: float


class TrendPoint(BaseModel):
    """Un punto de la serie temporal de KPIs de mejora (últimas N partidas válidas).

    Orden cronológico ascendente (partida más antigua primero) para que las gráficas de
    línea recorran el tiempo de izquierda a derecha. `timestamp` es la hora de juego en UTC.
    """

    game_id: str
    timestamp: datetime
    cs_min: float
    dpm: float
    kda: float


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


class Nemesis(BaseModel):
    enemy_champion: str
    games: int
    wins: int
    winrate: float
    avg_deaths: float
    avg_cs_min: float


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


class ConstitutionStatus(BaseModel):
    """La regla anti-tilt, movida del sidebar de Streamlit al backend.

    Incluye la comprobación de champion pool contra la configuración **persistida**, de modo que
    la alerta de "has jugado algo fuera de tus mains" ya no depende de un `text_area` volátil.
    """

    state: Literal["STOP", "ON_FIRE", "NEUTRAL", "NO_DATA"]
    message: str
    loss_streak: int
    last_results: list[bool] = Field(description="Más reciente primero; True = victoria")

    last_champion: str | None = Field(default=None, description="Campeón de la última partida")
    off_pool: bool = Field(default=False, description="La última partida fue fuera del champion pool")
    champion_pool: list[str] = Field(default_factory=list, description="Pool declarado, para contexto")


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


class SyncAccepted(BaseModel):
    """Respuesta inmediata del POST /api/sync: el trabajo pesado corre en BackgroundTasks."""

    status: Literal["processing"]
    message: str


class SyncStatus(BaseModel):
    """Estado del sync en curso (o del último terminado), para el polling del frontend."""

    status: Literal["idle", "processing", "success", "error"]
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
    updated_at: datetime | None = None

    # Canónicos (solo lectura, no persistidos en DB)
    impact_ratings: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    champion_pool_max: int = CHAMPION_POOL_MAX
    display_timezone: str = "Europe/Madrid"
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


class ConfigOptions(BaseModel):
    """Valores canónicos que el frontend necesita y que NO debe duplicar.

    En Streamlit la lista de `impact_rating` estaba escrita a mano en dos sitios distintos (el
    formulario post-partida y el de edición), con el riesgo de que divergieran.
    """

    impact_ratings: list[str]
    regions: list[str]
    champion_pool_max: int
    display_timezone: str
    riot_id: str = Field(description="Riot ID por defecto, desde el .env (no es un secreto)")
    riot_region: str


# ───────────────────────────── metadatos (Data Dragon) ────────────────────────────

# Diccionarios "limpios": el JSON crudo de Data Dragon ronda 1-8 MB con stats, tags y HTML;
# aquí viajan sólo los campos que la UI pinta. Las claves son las mismas que usa Riot:
# campeones por id de Data Dragon ("LeeSin"), items y hechizos por id numérico ("3078", "4").


class ChampionMeta(BaseModel):
    id: str = Field(description="Id de Data Dragon ('LeeSin'), clave del dict")
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
