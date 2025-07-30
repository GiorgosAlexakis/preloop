"""
SpaceSync NATS Worker
Subscribes to NATS messages and triggers tracker synchronization.
"""

import asyncio
import json
import logging
import os
import datetime
import inspect
import nats
from nats.aio.client import Client as NATSClient
from nats.aio.errors import ErrNoServers
from nats.js.api import ConsumerConfig

import spacesync.tasks as tasks
from spacesync.config import logger


class SpaceSyncNatsWorker:
    def __init__(self, nats_url: str, subscribe_subject: str, queue_name: str):
        self.nats_url = nats_url
        self.subscribe_subject = subscribe_subject
        self.queue_name = queue_name
        self.nc: NATSClient = None
        self.js = None
        self.sub = None

    async def connect(self):
        if self.nc and self.nc.is_connected:
            logger.info("NATS client already connected.")
            return

        logger.info(f"Worker connecting to NATS server at {self.nats_url}")
        try:
            self.nc = await nats.connect(
                self.nats_url,
                name="spacesync-nats-worker",
            )
            self.js = self.nc.jetstream()
            logger.info(
                f"Worker successfully connected to NATS server: {self.nats_url}"
            )
        except ErrNoServers as e:
            logger.error(
                f"Worker could not connect to NATS: No servers available at {self.nats_url}. Error: {e}"
            )
            self.nc = None
            raise  # Reraise to indicate connection failure
        except Exception as e:
            logger.error(f"Worker error connecting to NATS at {self.nats_url}: {e}")
            self.nc = None
            raise  # Reraise

    async def start_listening(self):
        if not self.nc or not self.nc.is_connected:
            await self.connect()

        if not self.nc:  # Still not connected after attempt
            logger.error("Cannot start listening, NATS client not connected.")
            return

        logger.info(f"Worker subscribing to '{self.subscribe_subject}'")

        # Create a configuration object
        config = ConsumerConfig(
            durable_name="worker-group",
            ack_wait=180,
        )

        try:
            self.sub = await self.js.subscribe(
                subject=self.subscribe_subject, config=config
            )
        except Exception as e:
            logger.error(
                f"Failed to subscribe to NATS subject '{self.subscribe_subject}': {e}"
            )
            raise
        logger.info("Worker is now listening for messages.")

        # Process messages in a loop like worker.py
        async for msg in self.sub.messages:
            subject = msg.subject
            data = msg.data.decode()
            logger.info(f"Received message on '{subject}': {data}")

            start_time = datetime.datetime.now()

            try:
                payload = json.loads(data)

                if "event_source" in payload:
                    # This is a standardized event
                    logger.info(f"Processing standardized event: {payload}")
                    stats = await tasks.process_tracker_event(payload)
                elif "function" in payload:
                    # This is a legacy task
                    logger.info(f"Processing legacy task: {payload}")
                    func = getattr(tasks, payload["function"])
                    if inspect.iscoroutinefunction(func):
                        stats = await func(
                            *payload.get("args", []), **payload.get("kwargs", {})
                        )
                    else:
                        stats = func(
                            *payload.get("args", []), **payload.get("kwargs", {})
                        )
                else:
                    logger.error(f"Unknown message format: {data}")
                    await msg.ack()
                    continue

                # Acknowledge the message on success
                await msg.ack()
                end_time = datetime.datetime.now()
                logger.info(
                    f"Sync task for {payload.get('function')} completed and acknowledged. Stats: {stats}. Duration: {end_time - start_time}"
                )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON payload: {data}. Error: {e}")
                # Do not acknowledge the message, so it can be redelivered
            except AttributeError as e:
                logger.error(f"Task function not found: {e}")
                # Do not acknowledge the message, so it can be redelivered
            except Exception as e:
                logger.error(f"Error processing sync task: {e}", exc_info=True)
                # Do not acknowledge the message, so it can be redelivered
                # or handled by a dead-letter policy.

    async def stop(self):
        logger.info("Worker stop signal received.")
        if self.sub:
            try:
                await self.sub.unsubscribe()
                logger.info(f"Unsubscribed from '{self.subscribe_subject}'.")
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}")

        if self.nc and not self.nc.is_closed:
            logger.info("Closing worker NATS client connection...")
            try:
                await self.nc.close()
                logger.info("Worker NATS client connection closed.")
            except Exception as e:
                logger.error(f"Error closing worker NATS client connection: {e}")
        self.nc = None


async def main():
    # Configuration should ideally come from environment variables or a config file
    # Using spacebridge_settings.nats_url as an example, assuming it's accessible
    # and correctly configured for SpaceSync's environment.
    # If SpaceSync has its own settings management (e.g. spacesync_settings), use that.

    # Fallback to a default NATS URL if not found in settings, or make it mandatory.
    # Get NATS_URL directly from environment variables
    nats_server_url = os.getenv("NATS_URL", "nats://localhost:4222")

    subject_to_subscribe = "spacesync.tasks"
    queue = "spacesync_worker_queue"

    worker = SpaceSyncNatsWorker(
        nats_url=nats_server_url,
        subscribe_subject=subject_to_subscribe,
        queue_name=queue,
    )

    try:
        await worker.start_listening()
    except asyncio.CancelledError:
        logger.info("Worker task cancelled.")
    except ErrNoServers:
        logger.error(
            f"NATS Worker could not connect to {nats_server_url}. Ensure NATS is running and accessible."
        )
    except Exception as e:
        logger.error(f"NATS Worker encountered an unhandled error: {e}", exc_info=True)
    finally:
        logger.info("NATS Worker shutting down...")
        await worker.stop()
        logger.info("NATS Worker shutdown complete.")


if __name__ == "__main__":
    # Basic logging setup for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("NATS Worker interrupted by user (Ctrl+C). Exiting.")
