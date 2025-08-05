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
import socket
import uuid
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
        # Generate a unique name for the connection, not the consumer.
        self.connection_name = f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
        # Use the queue name as the durable name for the entire worker group.
        self.durable_name = self.queue_name

    async def connect(self):
        if self.nc and self.nc.is_connected:
            logger.info("NATS client already connected.")
            return

        logger.info(
            f"Worker '{self.connection_name}' connecting to NATS server at {self.nats_url}"
        )
        try:
            self.nc = await nats.connect(
                self.nats_url,
                name=self.connection_name,
            )
            self.js = self.nc.jetstream()
            logger.info(
                f"Worker '{self.connection_name}' successfully connected to NATS server: {self.nats_url}"
            )
        except ErrNoServers as e:
            logger.error(
                f"Worker '{self.connection_name}' could not connect to NATS: No servers available at {self.nats_url}. Error: {e}"
            )
            self.nc = None
            raise
        except Exception as e:
            logger.error(
                f"Worker '{self.connection_name}' error connecting to NATS at {self.nats_url}: {e}"
            )
            self.nc = None
            raise

    async def start_listening(self):
        if not self.nc or not self.nc.is_connected:
            await self.connect()

        if not self.nc:
            logger.error("Cannot start listening, NATS client not connected.")
            return

        logger.info(
            f"Worker '{self.connection_name}' subscribing to '{self.subscribe_subject}'"
        )

        try:
            # Create a durable consumer shared by all workers in the queue group.
            # The stream is expected to be created by a publisher.
            config = ConsumerConfig(
                durable_name=self.durable_name,
                ack_wait=180,  # 3 minutes
            )

            self.sub = await self.js.subscribe(
                subject=self.subscribe_subject,
                queue=self.queue_name,
                config=config,
            )
        except Exception as e:
            logger.error(
                f"Failed to subscribe to NATS subject '{self.subscribe_subject}': {e}"
            )
            raise
        logger.info(f"Worker '{self.connection_name}' is now listening for messages.")

        async for msg in self.sub.messages:
            subject = msg.subject
            data = msg.data.decode()
            logger.info(f"Received message on '{subject}': {data}")

            start_time = datetime.datetime.now()

            try:
                payload = json.loads(data)

                if "function" in payload:
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

                await msg.ack()
                end_time = datetime.datetime.now()
                logger.info(
                    f"Task '{payload.get('function')}' completed and acknowledged. Stats: {stats}. Duration: {end_time - start_time}"
                )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON payload: {data}. Error: {e}")
            except AttributeError as e:
                logger.error(f"Task function not found: {e}")
            except Exception as e:
                logger.error(f"Error processing task: {e}", exc_info=True)

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
