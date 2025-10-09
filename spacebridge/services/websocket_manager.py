import asyncio
import json
import logging
import uuid
from typing import Dict

from fastapi import WebSocket
from nats.aio.client import Client
from nats.aio.msg import Msg
from sqlalchemy import text

from spacesync.services.event_bus import get_task_publisher
from spacemodels.db.session import get_db_session as get_db

logger = logging.getLogger(__name__)


async def persist_execution_log(execution_id: str, log_data: dict):
    """
    Appends a log entry to the execution_logs array in the database.

    Args:
        execution_id: ID of the flow execution
        log_data: Log message data to append
    """
    try:
        db = next(get_db())
        try:
            # Use PostgreSQL's JSONB append operator to add log to array
            # If execution_logs is NULL, initialize it as an empty array first
            # Convert the dict to JSON string for proper JSONB casting
            log_json = json.dumps(log_data)
            db.execute(
                text("""
                    UPDATE flow_execution
                    SET execution_logs = COALESCE(execution_logs, '[]'::jsonb) || CAST(:log_entry AS jsonb)
                    WHERE id = :execution_id
                """),
                {"execution_id": execution_id, "log_entry": log_json},
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(
            f"Failed to persist log for execution {execution_id}: {e}", exc_info=True
        )


class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates.
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        """
        Accepts a new WebSocket connection and returns a unique ID for it.
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        logger.info(f"New WebSocket connection {connection_id} established.")
        logger.info(f"Total active connections: {len(self.active_connections)}")
        return connection_id

    def disconnect(self, connection_id: str):
        """
        Disconnects a WebSocket.
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"WebSocket connection {connection_id} closed.")
            logger.info(f"Total active connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """
        Broadcasts a message to all connected clients.
        """
        for connection_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except Exception:
                logger.warning(
                    f"Failed to send message to connection {connection_id}. It might be closed."
                )

    async def broadcast_json(self, data: dict):
        """
        Broadcasts a JSON message to all connected clients.
        """
        await self.broadcast(json.dumps(data))


async def nats_consumer(manager: "WebSocketManager"):
    """
    Consumes messages from NATS and broadcasts them to WebSocket clients.
    Also persists execution logs to the database.
    """
    task_publisher = await get_task_publisher()
    nats_client: Client = task_publisher.nc
    if not nats_client or not nats_client.is_connected:
        logger.error("NATS client not available or not connected.")
        return

    async def message_handler(msg: Msg):
        try:
            data = json.loads(msg.data.decode())

            # Persist log messages to database
            execution_id = data.get("execution_id")
            if execution_id:
                await persist_execution_log(execution_id, data)

            # Broadcast to WebSocket clients
            await manager.broadcast_json(data)
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message from NATS: {msg.data.decode()}")
        except Exception as e:
            logger.error(f"Error processing NATS message: {e}")

    try:
        # Subscribe to a wildcard subject to receive all flow updates
        sub = await nats_client.subscribe("flow-updates.*", cb=message_handler)
        logger.info("Subscribed to NATS subject 'flow-updates.*'")
        # Keep the consumer running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"NATS consumer failed: {e}")


# Create a single instance of the manager to be used across the application
manager = WebSocketManager()
