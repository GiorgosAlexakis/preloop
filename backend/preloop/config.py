"""Configuration for Preloop."""

import logging
import os

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Versioning
SERVER_VERSION = "0.3.0"  # Current server version
MIN_CLIENT_VERSION = "0.3.0"  # Minimum compatible client version
MAX_CLIENT_VERSION = "0.3.0"  # Maximum recommended client version


class DatabaseSettings(BaseModel):
    """Database configuration."""

    url: str = Field(..., description="Database URL")
    pool_size: int = Field(5, description="Database connection pool size")
    max_overflow: int = Field(10, description="Maximum number of overflow connections")
    pool_timeout: int = Field(30, description="Pool timeout in seconds")
    pool_recycle: int = Field(1800, description="Pool recycle time in seconds")


class SecuritySettings(BaseModel):
    """Security configuration."""

    secret_key: str = Field(..., description="Secret key for JWT tokens")
    token_expire_minutes: int = Field(
        30, description="Token expiration time in minutes"
    )
    algorithm: str = Field("HS256", description="JWT algorithm")


class ServerSettings(BaseModel):
    """Server configuration."""

    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    debug: bool = Field(False, description="Debug mode")
    allowed_origins: list[str] = Field(["*"], description="Allowed CORS origins")


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = Field("Preloop", description="Application name")
    version: str = Field(SERVER_VERSION, description="Application version")
    environment: str = Field(
        "development", description="Environment (development, production)"
    )
    log_level: str = Field("INFO", description="Log level")
    product_team_email: str = Field(
        "product@spacecode.ai", description="Product team email address"
    )
    nats_url: str = Field("nats://localhost:4222", description="NATS server URL")
    preloop_url: str = Field("http://localhost:8000", description="Preloop URL")
    PROMPTS_FILE: str = Field(
        "backend/preloop/prompts.yaml",
        description="Path to the prompts YAML file",
    )

    # Feature flags for self-hosted deployments
    registration_enabled: bool = Field(
        True,
        description="Enable self-registration. Set to False to require admin invitation.",
    )

    database: DatabaseSettings
    security: SecuritySettings
    server: ServerSettings

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    stripe_secret_key: str = Field(
        "",
        description="Stripe secret key",
    )
    stripe_webhook_secret: str = Field(
        "",
        description="Stripe webhook secret",
    )

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables.

        Returns:
            Settings: Application settings.
        """
        # Load required settings
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            database_url = "postgresql+psycopg://postgres:postgres@localhost/preloop"
            logger.warning(f"DATABASE_URL not set, using default: {database_url}")

        secret_key = os.getenv("SECRET_KEY")
        if not secret_key:
            secret_key = "development_secret_key_do_not_use_in_production"
            logger.warning("SECRET_KEY not set, using default development key")

        # Create database settings
        database = DatabaseSettings(
            url=database_url,
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DATABASE_POOL_RECYCLE", "1800")),
        )

        # Create security settings
        security = SecuritySettings(
            secret_key=secret_key,
            token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
            algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        )

        # Create server settings
        server = ServerSettings(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "8000")),
            debug=os.getenv("DEBUG", "False").lower() in ("true", "1", "t"),
            allowed_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
        )

        prompts_file = os.getenv("PROMPTS_PATH", "backend/preloop/prompts.yaml")

        # Stripe configuration - no default keys for security
        # Self-hosted deployments must supply their own keys if billing is enabled
        stripe_secret_key = os.getenv("STRIPE_SECRET_KEY", "")
        stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

        # Feature flags
        registration_enabled = os.getenv("REGISTRATION_ENABLED", "true").lower() in (
            "true",
            "1",
            "t",
            "yes",
        )

        return cls(
            app_name=os.getenv("APP_NAME", "Preloop"),
            environment=os.getenv("ENVIRONMENT", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            product_team_email=os.getenv("PRODUCT_TEAM_EMAIL", "product@spacecode.ai"),
            nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
            PROMPTS_FILE=prompts_file,
            registration_enabled=registration_enabled,
            database=database,
            security=security,
            server=server,
            stripe_secret_key=stripe_secret_key,
            stripe_webhook_secret=stripe_webhook_secret,
        )


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Settings: Application settings.
    """
    return Settings.from_env()


# Create settings instance
settings = get_settings()
