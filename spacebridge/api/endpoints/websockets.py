import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from spacebridge.services.websocket_manager import manager
from spacemodels.db.session import get_db_session as get_db
from spacemodels.crud import crud_flow_execution
from spacesync.services.event_bus import EventBus

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


@router.websocket("/ws/flow-executions/{execution_id}")
async def flow_execution_websocket(
    websocket: WebSocket,
    execution_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for bidirectional flow execution monitoring.

    Streams:
    - Real-time logs from agent execution (line-by-line)
    - Status updates (every 5 seconds)
    - Parsed actions and MCP calls

    Accepts commands:
    - {"command": "stop"} - Stop execution
    - {"command": "send_message", "message": "..."} - Send message to agent
    - {"command": "pause"} - Pause execution (future)

    Args:
        websocket: WebSocket connection
        execution_id: UUID of the flow execution to monitor
        db: Database session
    """
    await websocket.accept()

    # Verify execution exists
    execution = crud_flow_execution.get(db, id=execution_id)
    if not execution:
        await websocket.send_json({"error": "Execution not found"})
        await websocket.close(code=1008)
        return

    # TODO: Add authorization check - verify user has access to this execution's flow

    # Connect to NATS event bus
    event_bus = EventBus()
    nats_sub = None

    try:
        await event_bus.connect()
        logger.info(f"WebSocket connected for execution {execution_id}")

        # Subscribe to NATS updates for this execution
        update_subject = f"flow-updates.{execution_id}"

        async def nats_message_handler(msg):
            """Forward NATS messages to WebSocket client."""
            try:
                data = json.loads(msg.data.decode())
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error forwarding NATS message to WebSocket: {e}")

        nats_sub = await event_bus.nc.subscribe(update_subject, cb=nats_message_handler)
        logger.info(f"Subscribed to NATS subject: {update_subject}")

        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "execution_id": execution_id,
                "message": "Connected to flow execution stream",
            }
        )

        # Listen for commands from WebSocket client
        while True:
            try:
                data = await websocket.receive_json()

                # Validate command structure
                if "command" not in data:
                    await websocket.send_json({"error": "Missing 'command' field"})
                    continue

                command = data["command"]
                logger.info(
                    f"Received command '{command}' for execution {execution_id}"
                )

                # Publish command to NATS for orchestrator to handle
                command_subject = f"flow-commands.{execution_id}"
                await event_bus.nc.publish(command_subject, json.dumps(data).encode())

                # Acknowledge command
                await websocket.send_json(
                    {
                        "type": "command_ack",
                        "command": command,
                        "message": f"Command '{command}' sent",
                    }
                )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for execution {execution_id}")
                break
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
                await websocket.send_json({"error": f"Error processing message: {e}"})

    except Exception as e:
        logger.error(
            f"Error in WebSocket connection for execution {execution_id}: {e}",
            exc_info=True,
        )
        await websocket.send_json({"error": f"Connection error: {e}"})

    finally:
        # Cleanup
        if nats_sub:
            try:
                await nats_sub.unsubscribe()
            except Exception as e:
                logger.error(f"Error unsubscribing from NATS: {e}")

        try:
            await event_bus.close()
        except Exception as e:
            logger.error(f"Error closing NATS connection: {e}")

        try:
            await websocket.close()
        except Exception:
            pass  # Already closed

        logger.info(f"WebSocket connection closed for execution {execution_id}")
