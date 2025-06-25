"""
SpaceSync NATS Worker
Subscribes to NATS messages and triggers tracker synchronization.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, List

import os # Added to access environment variables
import nats
from nats.aio.client import Client as NATSClient
from nats.aio.errors import ErrNoServers
from sqlalchemy.orm import Session

from spacemodels.crud import crud_tracker
from spacemodels.db.session import get_db_session
from spacemodels.models import Organization
from spacesync.config import logger as spacesync_logger # Removed settings import
from spacesync.scanner.core import TrackerClient, _process_organization, POLLING_THRESHOLD # POLLING_THRESHOLD might be needed
from spacesync.exceptions import TrackerRateLimitError

# Configure logger for the worker
logger = spacesync_logger # Use the existing SpaceSync logger or configure a new one
# Example: logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO) # etc.


class SpaceSyncNatsWorker:
    def __init__(self, nats_url: str, subscribe_subject: str, queue_name: str):
        self.nats_url = nats_url
        self.subscribe_subject = subscribe_subject
        self.queue_name = queue_name
        self.nc: Optional[NATSClient] = None
        self._stop_event = asyncio.Event()

    async def connect(self):
        if self.nc and self.nc.is_connected:
            logger.info("NATS client already connected.")
            return

        logger.info(f"Worker connecting to NATS server at {self.nats_url}")
        try:
            self.nc = await nats.connect(
                self.nats_url,
                error_cb=self._error_cb,
                reconnected_cb=self._reconnected_cb,
                disconnected_cb=self._disconnected_cb,
                closed_cb=self._closed_cb,
                name="spacesync-nats-worker",
            )
            logger.info(f"Worker successfully connected to NATS server: {self.nats_url}")
        except ErrNoServers as e:
            logger.error(
                f"Worker could not connect to NATS: No servers available at {self.nats_url}. Error: {e}"
            )
            self.nc = None
            raise  # Reraise to indicate connection failure
        except Exception as e:
            logger.error(f"Worker error connecting to NATS at {self.nats_url}: {e}")
            self.nc = None
            raise # Reraise

    async def _error_cb(self, e: Exception):
        logger.error(f"Worker NATS client error: {e}")

    async def _reconnected_cb(self):
        logger.info(f"Worker NATS client reconnected to {self.nats_url}")

    async def _disconnected_cb(self):
        logger.warning("Worker NATS client disconnected.")

    async def _closed_cb(self):
        logger.info("Worker NATS client connection closed.")

    async def message_handler(self, msg):
        subject = msg.subject
        data = msg.data.decode()
        logger.info(f"Received message on '{subject}': {data}")

        try:
            payload = json.loads(data)
            tracker_id = payload.get("tracker_id")
            if not tracker_id:
                logger.error("No tracker_id found in message payload.")
                return
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON payload: {data}")
            return
        except Exception as e:
            logger.error(f"Error processing message payload: {e}")
            return

        logger.info(f"Starting synchronization for tracker_id: {tracker_id}")

        # This is the core logic adapted from the old update_tracker function
        stats = {
            "organizations_scanned": 0,
            "organizations_skipped_webhook": 0,
            "organizations_skipped_polling": 0,
            "projects": 0,
            "issues": 0,
            "embeddings_updated": 0,
            "errors": 0,
        }
        rate_limited_tracker = False

        db: Optional[Session] = None
        session_generator = get_db_session()
        try:
            db = next(session_generator)
            tracker = crud_tracker.get_by_id(db, id=tracker_id)
            if not tracker:
                logger.error(f"Tracker {tracker_id} not found in database.")
                stats["errors"] += 1
                return # No point continuing

            tracker_client = TrackerClient(tracker) # From spacesync.scanner.core
            # Use epoch time for full scan, as per original logic
            since = datetime(1970, 1, 1)
            force_update = False # Default for scheduled/event-driven jobs

            try:
                tracker_organizations: List[Organization] = tracker_client.scan_organizations(db)
                if not tracker_organizations:
                    logger.info(f"No active organizations found for tracker {tracker_id}. Sync cycle complete.")
                    return
            except TrackerRateLimitError as rle:
                logger.warning(f"Rate limit hit for tracker {tracker_id} during organization scan. Details: {rle}")
                rate_limited_tracker = True
                tracker_organizations = []
                stats["errors"] += 1
            except Exception as e:
                logger.error(f"Failed to get organizations for tracker {tracker_id}: {e}", exc_info=True)
                stats["errors"] += 1
                return

            for org in tracker_organizations:
                if rate_limited_tracker:
                    logger.warning(f"Skipping remaining organizations for tracker {tracker_id} due to prior rate limit.")
                    break

                try:
                    # _process_organization is synchronous.
                    # If it becomes very long-running, consider asyncio.to_thread (Python 3.9+)
                    # or a ThreadPoolExecutor for true non-blocking behavior.
                    # For now, direct call as it involves DB and potentially blocking I/O.
                    org_stats, skipped = _process_organization(
                        db=db,
                        client=tracker_client,
                        org=org,
                        since=since,
                        force_update=force_update,
                    )

                    if skipped:
                        now = datetime.utcnow()
                        if org.last_webhook_update and (now - org.last_webhook_update) < POLLING_THRESHOLD:
                            stats["organizations_skipped_webhook"] += 1
                        elif org.last_polling_update and (now - org.last_polling_update) < POLLING_THRESHOLD:
                            stats["organizations_skipped_polling"] += 1
                    else:
                        stats["organizations_scanned"] += 1
                        stats["projects"] += org_stats["projects"]
                        stats["issues"] += org_stats["issues"]
                        stats["embeddings_updated"] += org_stats["embeddings_updated"]
                        stats["errors"] += org_stats["errors"]

                except TrackerRateLimitError as rle:
                    logger.warning(f"Rate limit hit for tracker {tracker_id} while processing org {org.identifier}. Details: {rle}")
                    rate_limited_tracker = True
                    stats["errors"] += 1
                except Exception as e:
                    logger.error(f"Unexpected error processing organization {org.identifier} for tracker {tracker_id}: {e}", exc_info=True)
                    stats["errors"] += 1

            logger.info(f"Finished synchronization for tracker {tracker_id}. Stats: {stats}. Rate limited: {rate_limited_tracker}")

        except StopIteration:
            logger.error(f"Failed to get database session from generator for tracker {tracker_id}.")
            stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error during NATS worker processing for tracker {tracker_id}: {e}", exc_info=True)
            stats["errors"] += 1 # Ensure error is counted if it happens before stats dict is fully populated
        finally:
            if db:
                try:
                    db.close()
                    logger.debug(f"Closed DB session for tracker {tracker_id} in NATS worker.")
                except Exception as close_exc:
                    logger.error(f"Error closing DB session for tracker {tracker_id} in NATS worker: {close_exc}")

    async def start_listening(self):
        if not self.nc or not self.nc.is_connected:
            await self.connect()

        if not self.nc: # Still not connected after attempt
            logger.error("Cannot start listening, NATS client not connected.")
            return

        logger.info(f"Worker subscribing to '{self.subscribe_subject}' with queue '{self.queue_name}'")
        self.sub = await self.nc.subscribe(
            self.subscribe_subject, queue=self.queue_name, cb=self.message_handler
        )
        logger.info("Worker is now listening for messages.")

        # Keep the listener alive until stop event is set
        await self._stop_event.wait()

    async def stop(self):
        logger.info("Worker stop signal received.")
        self._stop_event.set()
        if hasattr(self, 'sub') and self.sub:
            try:
                await self.nc.unsubscribe(self.sub)
                logger.info(f"Unsubscribed from '{self.subscribe_subject}'.")
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}")

        if self.nc and not self.nc.is_closed:
            logger.info("Closing worker NATS client connection...")
            try:
                await self.nc.drain()
                logger.info("Worker NATS client connection drained and closed.")
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

    subject_to_subscribe = "spacebridge.internal.tracker.sync_request.*"
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
        logger.error(f"NATS Worker could not connect to {nats_server_url}. Ensure NATS is running and accessible.")
    except Exception as e:
        logger.error(f"NATS Worker encountered an unhandled error: {e}", exc_info=True)
    finally:
        logger.info("NATS Worker shutting down...")
        await worker.stop()
        logger.info("NATS Worker shutdown complete.")


if __name__ == "__main__":
    # Basic logging setup for standalone execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("NATS Worker interrupted by user (Ctrl+C). Exiting.")
