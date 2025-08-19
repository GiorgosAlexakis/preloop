import os
import logging

logger = logging.getLogger(__name__)


def init_sentry():
    # Initialize Sentry if DSN is configured
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        import sentry_sdk  # noqa: F401

        if os.getenv("SPACEBRIDGE_URL") == "https://staging.spacebridge.io":
            sentry_env = "staging"
        elif os.getenv("SPACEBRIDGE_URL") == "https://spacebridge.io":
            sentry_env = "production"
        else:
            sentry_env = "development"

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
