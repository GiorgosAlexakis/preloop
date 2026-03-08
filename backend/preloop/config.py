"""Configuration for Preloop."""

import logging
import os
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _load_release_version(
    default: str = "0.8.0", version_file: Path | None = None
) -> str:
    """Load the repository release version from the canonical VERSION file."""
    if version_file is None:
        version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("Could not read %s, using fallback version", version_file)
        return default

    if not version:
        logger.warning("%s is empty, using fallback version", version_file)
        return default

    return version


# Versioning
SERVER_VERSION = _load_release_version()
MIN_CLIENT_VERSION = SERVER_VERSION
MAX_CLIENT_VERSION = SERVER_VERSION


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
    encryption_key: str = Field(
        "",
        description="Fernet encryption key for sensitive data (32 url-safe base64-encoded bytes). "
        "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'",
    )
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


class GitHubAppSettings(BaseModel):
    """GitHub App OAuth configuration (SaaS only).

    These settings are required for GitHub App OAuth integration.
    When configured, enables "Connect with GitHub" flow for tracker creation.
    """

    app_id: str = Field("", description="GitHub App ID")
    client_id: str = Field("", description="GitHub App Client ID")
    client_secret: str = Field("", description="GitHub App Client Secret")
    private_key: str = Field(
        "", description="GitHub App Private Key (PEM format, base64 encoded)"
    )
    webhook_secret: str = Field(
        "", description="GitHub App Webhook Secret for signature verification"
    )
    slug: str = Field(
        "", description="GitHub App slug (e.g., 'preloop' or 'preloop-staging')"
    )

    @property
    def is_configured(self) -> bool:
        """Check if GitHub App is fully configured."""
        return bool(
            self.app_id
            and self.client_id
            and self.client_secret
            and self.private_key
            and self.webhook_secret
            and self.slug
        )


class GoogleOAuthSettings(BaseModel):
    """Google OAuth configuration for sign-in/sign-up."""

    client_id: str = Field("", description="Google OAuth Client ID")
    client_secret: str = Field("", description="Google OAuth Client Secret")


class GitLabOAuthSettings(BaseModel):
    """GitLab OAuth configuration for sign-in/sign-up.

    Works with GitLab.com by default. For self-hosted GitLab, set
    GITLAB_OAUTH_BASE_URL to your instance URL (e.g. https://gitlab.example.com).
    """

    client_id: str = Field("", description="GitLab OAuth Application ID")
    client_secret: str = Field("", description="GitLab OAuth Application Secret")
    base_url: str = Field(
        "https://gitlab.com",
        description="GitLab instance URL (for self-hosted)",
    )


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = Field("Preloop", description="Application name")
    version: str = Field(SERVER_VERSION, description="Application version")
    environment: str = Field(
        "development", description="Environment (development, production)"
    )
    log_level: str = Field("INFO", description="Log level")
    product_team_email: str = Field("", description="Product team email address")
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
    github_app: GitHubAppSettings = Field(
        default_factory=GitHubAppSettings,
        description="GitHub App OAuth settings (SaaS only)",
    )
    google_oauth: GoogleOAuthSettings = Field(
        default_factory=GoogleOAuthSettings,
        description="Google OAuth settings for sign-in/sign-up",
    )
    gitlab_oauth: GitLabOAuthSettings = Field(
        default_factory=GitLabOAuthSettings,
        description="GitLab OAuth settings for sign-in/sign-up",
    )

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

    # Notification webhooks for admin alerts
    slack_webhook_url: str = Field(
        "",
        description="Slack webhook URL for admin notifications",
    )
    mattermost_webhook_url: str = Field(
        "",
        description="Mattermost webhook URL for admin notifications",
    )
    installer_audit_account_id: str = Field(
        "",
        description="Account ID used to store public installer download audit events",
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
            encryption_key=os.getenv("SECURITY__ENCRYPTION_KEY", ""),
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

        # GitHub App OAuth settings (SaaS only)
        github_app = GitHubAppSettings(
            app_id=os.getenv("GITHUB_APP_ID", ""),
            client_id=os.getenv("GITHUB_APP_CLIENT_ID", ""),
            client_secret=os.getenv("GITHUB_APP_CLIENT_SECRET", ""),
            private_key=os.getenv("GITHUB_APP_PRIVATE_KEY", ""),
            webhook_secret=os.getenv("GITHUB_APP_WEBHOOK_SECRET", ""),
            slug=os.getenv("GITHUB_APP_SLUG", ""),
        )

        # Google OAuth settings
        google_oauth = GoogleOAuthSettings(
            client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        )

        # GitLab OAuth settings
        gitlab_oauth = GitLabOAuthSettings(
            client_id=os.getenv("GITLAB_OAUTH_CLIENT_ID", ""),
            client_secret=os.getenv("GITLAB_OAUTH_CLIENT_SECRET", ""),
            base_url=os.getenv("GITLAB_OAUTH_BASE_URL", "https://gitlab.com"),
        )

        return cls(
            app_name=os.getenv("APP_NAME", "Preloop"),
            environment=os.getenv("ENVIRONMENT", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            product_team_email=os.getenv("PRODUCT_TEAM_EMAIL", ""),
            nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
            PROMPTS_FILE=prompts_file,
            registration_enabled=registration_enabled,
            database=database,
            security=security,
            server=server,
            github_app=github_app,
            google_oauth=google_oauth,
            gitlab_oauth=gitlab_oauth,
            stripe_secret_key=stripe_secret_key,
            stripe_webhook_secret=stripe_webhook_secret,
            installer_audit_account_id=os.getenv("INSTALLER_AUDIT_ACCOUNT_ID", ""),
        )


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Settings: Application settings.
    """
    return Settings.from_env()


# Create settings instance
settings = get_settings()
