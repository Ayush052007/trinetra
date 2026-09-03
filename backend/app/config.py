"""TRINETRA runtime configuration.

Every value here is overridable through environment variables or a .env file.
No secret is ever hardcoded: SECRET_KEY has no usable default in production
mode and the application refuses to start without it (see validate_runtime).
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Identity -------------------------------------------------------
    APP_NAME: str = "TRINETRA"
    APP_TAGLINE: str = "Connecting Data. Revealing Networks. Empowering Investigations."
    APP_SUBTITLE: str = "AI-Powered Criminal Network Intelligence Platform"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | production

    # ---- Deployment identity (shown in the UI, configurable per install) --
    DEPLOYMENT_UNIT: str = "Criminal Network Intelligence Unit"
    DEPLOYMENT_ORG: str = "National Crime Records Bureau"
    DEPLOYMENT_DIVISION: str = "Women Safety Division"

    # ---- Data classification --------------------------------------------
    # The seeded corpus is synthetic. This banner is a data-integrity control,
    # not decoration: it must stay on until a deployment loads authorised data.
    DATA_CLASSIFICATION: str = "SYNTHETIC"
    SHOW_CLASSIFICATION_BANNER: bool = True

    # ---- Security --------------------------------------------------------
    SECRET_KEY: str = Field(default="")
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_HOURS: int = 8
    REMEMBER_ME_DAYS: int = 7
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20
    API_RATE_LIMIT_PER_MINUTE: int = 300
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # ---- Serverless mode -------------------------------------------------
    # Set on platforms that recreate the process per request (Vercel, Lambda).
    # Disables the startup warm-up thread and the WebSocket route, neither of
    # which can work when nothing survives between invocations.
    SERVERLESS: bool = False

    # ---- First-boot seeding ----------------------------------------------
    # On a cloud host there is no shell to run the seed from, so the app can
    # populate an empty database itself on first boot. It only ever runs when
    # the users table is empty, so it cannot overwrite existing data.
    AUTO_SEED: bool = False
    SEED_WITH_CORPUS: bool = True

    # ---- Storage ---------------------------------------------------------
    DATABASE_URL: str = f"sqlite:///{(PROJECT_ROOT / 'trinetra.db').as_posix()}"
    UPLOAD_DIR: str = str(PROJECT_ROOT / "uploads")
    MAX_UPLOAD_MB: int = 25

    # ---- Knowledge graph backend ----------------------------------------
    # "embedded" runs the in-process pure-Python graph engine (default, no
    # external service). "neo4j" switches every graph call to real Cypher.
    GRAPH_BACKEND: str = "embedded"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"

    # ---- Maps ------------------------------------------------------------
    # Empty = fully offline self-contained renderer. Set to an XYZ tile
    # template (e.g. OpenStreetMap) to overlay real tiles when online.
    MAP_TILE_URL: str = ""
    MAP_ATTRIBUTION: str = ""

    # ---- External integrations (NOT connected) ---------------------------
    # These stay false until a deployment supplies authorised credentials.
    # See docs/INTEGRATIONS.md. The UI reads these to label capabilities
    # honestly rather than implying a live connection.
    ENABLE_DEVICE_GPS: bool = False
    ENABLE_EMERGENCY_DISPATCH: bool = False
    ENABLE_SMS_GATEWAY: bool = False
    ENABLE_TELECOM_CDR_FEED: bool = False
    ENABLE_RTO_LOOKUP: bool = False
    ENABLE_CCTNS_SYNC: bool = False

    # True when a throwaway development key had to be generated.
    ephemeral_secret: bool = False

    def model_post_init(self, __context) -> None:
        # Resolve SECRET_KEY eagerly. Its absence in production is fatal and is
        # reported by validate_runtime(); development gets a per-process key so
        # nothing that issues tokens can ever observe an empty secret.
        if not self.SECRET_KEY and self.ENVIRONMENT != "production":
            object.__setattr__(self, "SECRET_KEY", secrets.token_urlsafe(48))
            object.__setattr__(self, "ephemeral_secret", True)

    @field_validator("ENVIRONMENT")
    @classmethod
    def _env_known(cls, v: str) -> str:
        if v not in {"development", "production", "test"}:
            raise ValueError("ENVIRONMENT must be development, production or test")
        return v

    @field_validator("GRAPH_BACKEND")
    @classmethod
    def _graph_known(cls, v: str) -> str:
        if v not in {"embedded", "neo4j"}:
            raise ValueError("GRAPH_BACKEND must be 'embedded' or 'neo4j'")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def validate_runtime(self) -> list[str]:
        """Return startup warnings; raise on unsafe production configuration."""
        warnings: list[str] = []
        if not self.SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY must be set in production. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if self.ephemeral_secret:
            warnings.append(
                "SECRET_KEY not set - generated an ephemeral development key. "
                "All sessions are invalidated on restart. Set SECRET_KEY in .env."
            )
        if self.GRAPH_BACKEND == "neo4j" and not self.NEO4J_PASSWORD:
            raise RuntimeError("GRAPH_BACKEND=neo4j requires NEO4J_PASSWORD.")
        if self.is_production and self.DATABASE_URL.startswith("sqlite"):
            warnings.append(
                "Running production on SQLite. PostgreSQL is recommended: "
                "set DATABASE_URL=postgresql+psycopg://user:pass@host/trinetra"
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
