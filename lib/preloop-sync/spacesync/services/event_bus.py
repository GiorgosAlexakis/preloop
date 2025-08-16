import nats
from nats.aio.client import Client as NATSClient
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
from nats.js.api import StreamConfig
from nats.js.errors import APIError

import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

import json
from spacebridge.config import settings


logger = logging.getLogger(__name__)


class TaskPublisher:
    def __init__(self):
        self.nc: Optional[NATSClient] = None
        self.js = None
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

            # Define the desired stream configuration
            config = StreamConfig(
                name="tasks",
                subjects=["spacesync.tasks"],
                retention="limits",
            )

            # Check if the stream exists and update if its configuration is different
            try:
                stream = await self.js.stream_info("tasks")
                # The retention policy cannot be changed, so we only update the subjects.
                if set(stream.config.subjects) != set(config.subjects):
                    logger.warning(
                        "Stream 'tasks' exists with different subjects. Updating..."
                    )
                    await self.js.update_stream(config)
                    logger.info("Stream 'tasks' subjects updated successfully.")
            except APIError as e:
                if e.err_code == 10059:  # Stream not found
                    logger.info("Stream 'tasks' not found. Creating it...")
                    await self.js.add_stream(config)
                    logger.info("Stream 'tasks' created successfully.")
                else:
                    raise e

            logger.info(f"Successfully connected to NATS server: {self.nats_url}")
        except ErrNoServers as e:
            logger.error(
                f"Could not connect to NATS: No servers available at {self.nats_url}. Error: {e}"
            )
            self.nc = None
            self.js = None
        except Exception as e:
            logger.error(f"Error connecting to NATS at {self.nats_url}: {e}")
            self.nc = None
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
        wait=wait_fixed(2),
        retry=retry_if_exception_type((ErrTimeout, ErrConnectionClosed)),
        reraise=True,
    )
    async def publish_task(self, function_name: str, *args, **kwargs):
        """
        Publishes a task to the NATS 'spacesync.tasks' subject.
        """
        if not self.js:
            logger.error("JetStream not initialized. Cannot publish task.")
            # Optionally, attempt to connect here or raise an exception
            await self.connect()
            if not self.js:
                logger.error("Failed to reconnect to NATS. Task not published.")
                return None

        subject = "spacesync.tasks"
        task_payload = {"function": function_name, "args": args, "kwargs": kwargs}
        payload_bytes = json.dumps(task_payload).encode("utf-8")

        try:
            ack = await self.js.publish(subject, payload_bytes)
            logger.info(
                f"Published task '{function_name}', Stream: {ack.stream}, Seq: {ack.seq}"
            )
            return ack
        except (ErrTimeout, ErrConnectionClosed) as e:
            logger.error(
                f"Failed to publish task '{function_name}' to NATS subject '{subject}' after multiple retries: {e}"
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while publishing task '{function_name}' to NATS subject '{subject}': {e}"
            )
        return None

    async def close(self):
        if self.nc and not self.nc.is_closed:
            logger.info("Closing NATS client connection...")
            try:
                await self.nc.drain()
                logger.info("NATS client connection drained and closed.")
            except Exception as e:
                logger.error(f"Error closing NATS client connection: {e}")
        else:
            logger.info("NATS client connection already closed or not established.")
        self.nc = None
        self.js = None


# Global instance for FastAPI dependency injection
task_publisher_service = TaskPublisher()


async def get_task_publisher() -> TaskPublisher:
    if task_publisher_service.nc is None or not task_publisher_service.nc.is_connected:
        logger.warning(
            "Task publisher accessed but not connected. Ensure connect() is called on app startup."
        )
    return task_publisher_service


# Functions to be called by FastAPI startup/shutdown events
async def connect_nats():
    await task_publisher_service.connect()


async def close_nats():
    await task_publisher_service.close()

    async def publish_resync_organization(self, organization_id: str):
        """
        Publishes a task to resync an organization.
        """
        await self.publish_task(
            "scan_tracker_task",
            kwargs={"tracker_id": organization_id, "force_update": True},
        )
