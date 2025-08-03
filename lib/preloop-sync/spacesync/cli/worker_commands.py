import click
import asyncio
import logging
from spacesync.services.nats_worker import main


@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
    help="Set the logging level.",
    show_default=True,
)
@click.command(name="worker")
def worker_cmd(log_level: str):
    """
    Start the SpaceSync worker service in the foreground.
    """
    logging.basicConfig(level=log_level)
    asyncio.run(main())
