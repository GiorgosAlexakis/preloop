import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from spacebridge.services.websocket_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming Flow execution updates.
    Includes a heartbeat to keep the connection alive.
    """
    connection_id = await manager.connect(websocket)
    try:
        while True:
            # Wait for a message from the client (e.g., a pong response)
            # Set a timeout to detect unresponsive clients.
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                if message == "pong":
                    # Client is alive
                    continue

                # Log user interaction events
                try:
                    event_data = json.loads(message)
                    logger.info(
                        f"Received user interaction event from {connection_id}: {event_data}"
                    )
                except json.JSONDecodeError:
                    logger.warning(
                        f"Received non-JSON message from {connection_id}: {message}"
                    )

            except asyncio.TimeoutError:
                # No message received in time, send a ping.
                await websocket.send_text("ping")
                # Wait for a pong response
                try:
                    response = await asyncio.wait_for(
                        websocket.receive_text(), timeout=10.0
                    )
                    if response != "pong":
                        break
                except asyncio.TimeoutError:
                    break  # Client did not respond to ping, assume disconnected.
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(connection_id)
