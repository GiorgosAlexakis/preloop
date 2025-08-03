import nats
from nats.aio.client import Client as NATSClient
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from spacebridge.config import settings
from spacebridge.schemas.events import StandardizedNatsEvent


logger = logging.getLogger(__name__)


class NatsPublisher:
    def __init__(self):
        self.nc: Optional[NATSClient] = None
        self.nats_url: str = settings.nats_url

    async def connect(self):
        if self.nc and self.nc.is_connected:
            logger.info("NATS client already connected.")
            return

        logger.info(f"Connecting to NATS server at {self.nats_url}")
        try:
            self.nc = await nats.connect(
                self.nats_url,
                error_cb=self._error_cb,
                reconnected_cb=self._reconnected_cb,
                disconnected_cb=self._disconnected_cb,
                closed_cb=self._closed_cb,
                name="spacebridge-publisher",
            )
            self.js = self.nc.jetstream()
            self.stream = await self.js.add_stream(
                name="tasks", subjects=["spacesync.tasks"], retention="workqueue"
            )
            logger.info(f"Successfully connected to NATS server: {self.nats_url}")
        except ErrNoServers as e:
            logger.error(
                f"Could not connect to NATS: No servers available at {self.nats_url}. Error: {e}"
            )
            self.nc = None  # Ensure nc is None if connection failed
            self.js = None
        except Exception as e:
            logger.error(f"Error connecting to NATS at {self.nats_url}: {e}")
            self.nc = None  # Ensure nc is None if connection failed
            self.js = None

    async def _error_cb(self, e: Exception):
        logger.error(f"NATS client error: {e}")

    async def _reconnected_cb(self):
        logger.info(f"NATS client reconnected to {self.nats_url}")

    async def _disconnected_cb(self):
        logger.warning("NATS client disconnected.")

    async def _closed_cb(self):
        logger.info("NATS client connection closed.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),  # Wait 2 seconds between retries
        retry=retry_if_exception_type((ErrTimeout, ErrConnectionClosed)),
        reraise=True,  # Reraise the exception if all retries fail
    )
    async def _do_publish(self, subject: str, payload: bytes):
        """Internal method to perform the actual publish, wrapped with retry."""
        if not self.nc:  # Should not happen if connect was successful
            raise ErrConnectionClosed("NATS client not initialized.")
        ack = await self.js.publish(subject, payload)
        logger.info(f"Published task '{subject}', Stream: {ack.stream}, Seq: {ack.seq}")
        return ack

    async def publish_event(self, event: "StandardizedNatsEvent"):
        """
        Publishes a standardized event to the appropriate NATS subject.

        Args:
            event: A StandardizedNatsEvent object.
        """
        if not self.nc or not self.nc.is_connected:
            logger.info("NATS client not connected. Attempting to reconnect...")
            await self.connect()
            if not self.nc or not self.nc.is_connected:
                logger.error("Failed to reconnect to NATS. Event not published.")
                return None

        subject = f"spacebridge.events.{event.event_source}.{event.event_type}"
        payload = event.model_dump_json().encode("utf-8")

        try:
            ack = await self._do_publish(subject, payload)
            logger.info(f"Successfully published event to NATS subject '{subject}'")
            return ack
        except (
            ErrTimeout,
            ErrConnectionClosed,
        ) as e:  # Catch exceptions reraised by tenacity
            logger.error(
                f"Failed to publish event to NATS subject '{subject}' after multiple retries: {e}"
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while publishing event to NATS subject '{subject}': {e}"
            )
        return None

    async def close(self):
        if self.nc and not self.nc.is_closed:
            logger.info("Closing NATS client connection...")
            try:
                await self.nc.drain()  # Drain ensures all buffered messages are sent
                logger.info("NATS client connection drained and closed.")
            except Exception as e:
                logger.error(f"Error closing NATS client connection: {e}")
        else:
            logger.info("NATS client connection already closed or not established.")
        self.nc = None
        self.js = None


# Global instance for FastAPI dependency injection
nats_publisher_service = NatsPublisher()


async def get_nats_publisher() -> NatsPublisher:
    # The connection is managed by startup/shutdown events in the main app
    if nats_publisher_service.nc is None or not nats_publisher_service.nc.is_connected:
        # This might happen if accessed before startup or after shutdown,
        # or if initial connection failed.
        # Depending on strictness, could raise an error or attempt to connect.
        # For now, we rely on startup to have connected.
        logger.warning(
            "NATS publisher accessed but not connected. Ensure connect() is called on app startup."
        )
    return nats_publisher_service


# Functions to be called by FastAPI startup/shutdown events
async def connect_nats():
    await nats_publisher_service.connect()


async def close_nats():
    await nats_publisher_service.close()
