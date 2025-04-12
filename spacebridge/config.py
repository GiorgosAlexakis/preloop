"""Configuration for SpaceBridge."""

import logging
import os

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Versioning
SERVER_VERSION = "0.1.0"  # Current server version
MIN_CLIENT_VERSION = "0.1.0"  # Minimum compatible client version
MAX_CLIENT_VERSION = "0.1.0"  # Maximum recommended client version


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

    app_name: str = Field("SpaceBridge", description="Application name")
    environment: str = Field(
        "development", description="Environment (development, production)"
    )
    log_level: str = Field("INFO", description="Log level")

    database: DatabaseSettings
    security: SecuritySettings
    server: ServerSettings

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
            database_url = (
                "postgresql+psycopg://postgres:postgres@localhost/spacebridge"
            )
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
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            allowed_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
        )

        # Create settings
        return cls(
            app_name=os.getenv("APP_NAME", "SpaceBridge"),
            environment=os.getenv("ENVIRONMENT", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database=database,
            security=security,
            server=server,
        )


# Create settings instance
settings = Settings.from_env()
