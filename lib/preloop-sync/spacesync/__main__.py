"""
Main entry point for SpaceSync.
"""

from .cli.commands import run
from spacemodels.sentry import init_sentry

if __name__ == "__main__":
    init_sentry()
    run()
