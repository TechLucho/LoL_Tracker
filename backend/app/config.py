"""Configuración centralizada. Valida las variables de entorno AL ARRANCAR.

El monolito Streamlit descubría credenciales ausentes a mitad de un request y las degradaba a
"no hay datos". Aquí un .env incompleto impide levantar el proceso, que es donde se debe notar.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Plataforma Riot -> ruta continental. Account-V1 y Match-V5 se enrutan por continente.
ROUTING_MAP = {
    "BR1": "americas", "LA1": "americas", "LA2": "americas", "NA1": "americas",
    "EUN1": "europe", "EUW1": "europe", "TR1": "europe", "RU": "europe",
    "JP1": "asia", "KR": "asia",
    "OC1": "sea", "PH2": "sea", "SG2": "sea", "TH2": "sea", "TW2": "sea", "VN2": "sea",
}


def _quote(value: object) -> str:
    """Escapa un valor para el formato keyword/value de libpq.

    Se usa este formato en vez de una URI porque la password de Supabase puede contener
    caracteres (`#`, `@`, `/`, `&`, `+`...) que romperían el parseo de una URI.
    """
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Riot ---
    riot_api_key: str = Field(min_length=10)
    riot_id: str = ""
    riot_region: str = "EUW1"

    # --- Supabase / Postgres ---
    db_host: str
    db_name: str
    db_user: str
    db_password: str
    db_port: int = 5432
    # TLS de libpq. Default "require": Supabase siempre va cifrado. Configurable porque el
    # postgres:16 efímero del CI (localhost, sin certificados) rechaza sslmode=require.
    db_sslmode: str = "require"

    # --- App ---
    # Zona en la que se interpretan las horas del heatmap "biológico". Los timestamps se guardan
    # en UTC; esta es sólo la zona de visualización. ASUNCIÓN: España (región EUW1 + UI española).
    display_timezone: str = "Europe/Madrid"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    app_api_token: str = ""  # si está vacío, la API queda abierta (uso local)
    pool_min_size: int = 1
    pool_max_size: int = 5
    sentry_dsn: str = ""  # si está vacío, Sentry no se inicializa

    @field_validator("riot_region")
    @classmethod
    def _known_region(cls, v: str) -> str:
        v = v.upper()
        if v not in ROUTING_MAP:
            raise ValueError(f"Región desconocida: {v}. Válidas: {', '.join(sorted(ROUTING_MAP))}")
        return v

    @property
    def continental_route(self) -> str:
        return ROUTING_MAP[self.riot_region]

    @property
    def dsn(self) -> str:
        """Conninfo de libpq. `sslmode=require` es explícito: Supabase siempre va por TLS."""
        parts = {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
            "sslmode": self.db_sslmode,
            "application_name": "lol_tracker_api",
        }
        return " ".join(f"{k}={_quote(v)}" for k, v in parts.items())


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
