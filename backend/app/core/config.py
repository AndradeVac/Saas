import os
import re
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ENVIRONMENT selects which .env file is loaded: development (default) or production.
# Files are resolved relative to backend/, so commands work from any directory.
# Real environment variables always win over values from the file.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
_env_file = BACKEND_DIR / f".env.{ENVIRONMENT}"
if not _env_file.exists():
    _env_file = BACKEND_DIR / ".env"

_INSECURE_SECRET = "development-only-change-this-secret"


class Settings(BaseSettings):
    environment: str = ENVIRONMENT
    log_level: str = "INFO"
    database_url: str
    jwt_secret_key: str = _INSECURE_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    # Comma-separated list of allowed browser origins. Each entry may be an exact origin
    # or a wildcard subdomain pattern such as https://*.mesadigital.app (one origin per tenant).
    frontend_url: str = "http://localhost:5173"
    # Public domain the tenants live under (<slug>.<root_domain>); used to build links.
    root_domain: str = "localhost"
    # Scheme and port appended to tenant links: "https" + "" in production, "http" + ":5173" locally.
    public_scheme: str = "http"
    public_port: str = ":5173"
    trial_days: int = 14
    # WhatsApp (with country code) the "Assinar" buttons open, e.g. 5511999990000. Empty hides the shortcut.
    sales_whatsapp: str = ""
    # Connection pool per API process (Neon's pooler fans these into its own limits).
    db_pool_size: int = 10
    db_max_overflow: int = 20
    # Uploaded images are stored in the database: per-file input limit and per-tenant quota.
    media_max_upload_mb: int = 6
    media_quota_mb: int = 100

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Hosting providers hand out postgres:// URLs; SQLAlchemy needs the psycopg (v3) driver name.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def cors_exact_origins(self) -> list[str]:
        return [origin for origin in self.cors_origins if "*" not in origin]

    @property
    def cors_origin_regex(self) -> str | None:
        """Wildcard entries (https://*.example.com) turned into one regex for CORSMiddleware."""
        patterns = [
            re.escape(origin).replace(r"\*", r"[a-z0-9-]+")
            for origin in self.cors_origins
            if "*" in origin
        ]
        return "^(" + "|".join(patterns) + ")$" if patterns else None

    def tenant_url(self, slug: str, path: str = "") -> str:
        return f"{self.public_scheme}://{slug}.{self.root_domain}{self.public_port}{path}"

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if not self.is_production:
            return self
        problems = []
        if self.jwt_secret_key == _INSECURE_SECRET or len(self.jwt_secret_key) < 32:
            problems.append("JWT_SECRET_KEY deve ser definido com pelo menos 32 caracteres")
        if any("localhost" in origin for origin in self.cors_origins):
            problems.append("FRONTEND_URL não pode apontar para localhost")
        if self.root_domain == "localhost":
            problems.append("ROOT_DOMAIN deve ser o domínio público da plataforma")
        if problems:
            raise ValueError("Configuração de produção inválida: " + "; ".join(problems))
        return self


settings = Settings()
