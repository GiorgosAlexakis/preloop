import os
import logging

logger = logging.getLogger(__name__)


def init_sentry():
    # Initialize Sentry if DSN is configured
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        import sentry_sdk  # noqa: F401

        sentry_env = ""
        try:
            from spacebridge.config import settings

            spacebridge_url = settings.spacebridge_url
        except ImportError:
            spacebridge_url = os.getenv("SPACEBRIDGE_URL")
        if spacebridge_url == "https://staging.spacebridge.io":
            sentry_env = "staging"
        elif spacebridge_url == "https://spacebridge.io":
            sentry_env = "production"
        elif "localhost" in spacebridge_url:
            sentry_env = "development"
        elif spacebridge_url:
            sentry_env = spacebridge_url.split(".")[0].split("//")[-1]

        if sentry_env:
            sentry_sdk.init(
                dsn=sentry_dsn,
                # Set traces_sample_rate to 1.0 to capture 100%
                # of transactions for performance monitoring.
                traces_sample_rate=1.0,
                # Set profiles_sample_rate to 1.0 to profile 100%
                # of sampled transactions.
                profiles_sample_rate=1.0,
                enable_tracing=True,
                environment=sentry_env,
            )
            logger.info("Sentry SDK initialized.")
