import asyncio
import json
import logging
import uuid
from typing import Dict

from fastapi import WebSocket
from nats.aio.client import Client
from nats.aio.msg import Msg

from spacesync.services.event_bus import get_task_publisher

logger = logging.getLogger(__name__)


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
    """
    task_publisher = await get_task_publisher()
    nats_client: Client = task_publisher.nc
    if not nats_client or not nats_client.is_connected:
        logger.error("NATS client not available or not connected.")
        return

    async def message_handler(msg: Msg):
        try:
            data = json.loads(msg.data.decode())
            # Here, you could add filtering logic based on execution_id
            # to send messages only to relevant clients.
            # For now, we broadcast to all.
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
