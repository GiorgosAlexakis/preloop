"""
Main entry point for preloop_sync.
"""

from .cli.commands import run
from preloop_models.sentry import init_sentry

if __name__ == "__main__":
    init_sentry()
    run()
