import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from spacebridge.api.auth import get_user_from_token_if_valid
from spacebridge.services.websocket_manager import manager
from spacebridge.services.session_manager import session_manager
from spacebridge.services.activity_tracker import handle_activity
from spacebridge.utils import get_client_ip
from spacemodels.db.session import get_db_session as get_db
from spacemodels.crud import crud_flow_execution, crud_flow
from spacesync.services.event_bus import EventBus

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for streaming Flow execution updates.
    Includes authentication and account-based filtering.
    Includes a heartbeat to keep the connection alive.

    Only broadcasts flow execution updates that belong to the authenticated user's account.
    """
    # Extract token from query parameters for authentication
    await websocket.accept()

    token = websocket.query_params.get("token")
    if not token:
        logger.warning("WebSocket connection attempted without token")
        await websocket.send_json({"error": "Authentication required - token missing"})
        await websocket.close(code=1008)
        return

    # Validate token and get user
    user = await get_user_from_token_if_valid(token, db)
    if not user:
        logger.warning("Invalid token for WebSocket connection")
        await websocket.send_json({"error": "Invalid or expired authentication token"})
        await websocket.close(code=1008)
        return

    logger.info(
        f"WebSocket authenticated for user {user.username} (account {user.account_id})"
    )

    # Connect with account_id for filtering
    connection_id = await manager.connect_with_account(websocket, str(user.account_id))

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

    # Extract token from query parameters for authentication
    token = websocket.query_params.get("token")
    if not token:
        logger.warning(
            f"WebSocket connection attempted without token for execution {execution_id}"
        )
        await websocket.send_json({"error": "Authentication required - token missing"})
        await websocket.close(code=1008)
        return

    # Validate token and get user
    user = await get_user_from_token_if_valid(token, db)
    if not user:
        logger.warning(
            f"Invalid token for WebSocket connection to execution {execution_id}"
        )
        await websocket.send_json({"error": "Invalid or expired authentication token"})
        await websocket.close(code=1008)
        return

    # Get the flow associated with this execution
    flow = crud_flow.get(db, id=execution.flow_id)
    if not flow:
        logger.error(f"Flow {execution.flow_id} not found for execution {execution_id}")
        await websocket.send_json({"error": "Flow not found"})
        await websocket.close(code=1008)
        return

    # Verify user has access to this flow
    if flow.account_id and flow.account_id != user.account_id:
        logger.warning(
            f"User {user.username} (account {user.account_id}) attempted to access flow {flow.id} "
            f"(account {flow.account_id}) via WebSocket for execution {execution_id}"
        )
        await websocket.send_json(
            {"error": "Unauthorized - you do not have access to this flow execution"}
        )
        await websocket.close(code=1008)
        return

    logger.info(
        f"WebSocket authorized for user {user.username} to access execution {execution_id}"
    )

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


@router.websocket("/ws/unified")
async def unified_websocket(websocket: WebSocket, db: Session = Depends(get_db)):
    """Unified WebSocket endpoint for all real-time updates.

    Features:
    - Single persistent connection per user
    - Supports authenticated and anonymous users
    - Activity tracking and analytics
    - Message routing to appropriate handlers
    - Automatic session management

    Query Parameters:
        token (optional): Authentication token for authenticated users
        fingerprint (optional): Browser fingerprint for anonymous users
    """
    await websocket.accept()

    # Extract parameters
    token = websocket.query_params.get("token")
    fingerprint = websocket.query_params.get("fingerprint")

    # Get real IP address (behind ingress)
    client_ip = get_client_ip(websocket)
    user_agent = websocket.headers.get("user-agent", "")

    # Authenticate user (optional for anonymous)
    user = None
    if token:
        user = await get_user_from_token_if_valid(token, db)
        if not user:
            logger.warning(f"Invalid token for unified WebSocket from {client_ip}")
            await websocket.send_json(
                {"error": "Invalid or expired authentication token"}
            )
            await websocket.close(code=1008)
            return

    # Create session
    session = await session_manager.create_session(
        websocket=websocket,
        user=user,
        fingerprint=fingerprint,
        ip_address=client_ip,
        user_agent=user_agent,
        db=db,
    )

    logger.info(
        f"Unified WebSocket session {session.id} established for "
        f"{'user ' + user.username if user else 'anonymous ' + (fingerprint[:8] if fingerprint else 'unknown')} "
        f"from {client_ip}"
    )

    # Start heartbeat monitoring
    heartbeat_task = None
    manager_connection_id = None

    try:
        # Register connection with the existing WebSocket manager for broadcast compatibility
        if user:
            manager_connection_id = await manager.connect_with_account(
                websocket, str(user.account_id)
            )
        else:
            # For anonymous users, register without account filtering
            manager_connection_id = str(session.connection_id)
            manager.active_connections[manager_connection_id] = websocket

        # Send initial handshake confirmation
        await websocket.send_json(
            {
                "type": "handshake",
                "session_id": session.id,
                "authenticated": session.is_authenticated,
                "message": "Connected to unified WebSocket",
            }
        )

        # Message loop
        while True:
            try:
                # Wait for message with timeout for heartbeat
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)

                # Update activity timestamp
                session_manager.update_activity(session.id)

                # Handle different message types
                message_type = data.get("type")

                if message_type == "activity":
                    # Handle activity tracking (page views, actions, conversions)
                    await handle_activity(data, session, db)

                elif message_type == "command":
                    # Handle commands (future: stop execution, etc.)
                    logger.info(
                        f"Received command from session {session.id}: {data.get('command')}"
                    )
                    # TODO: Route commands to appropriate handlers

                elif message_type == "subscribe":
                    # Handle topic subscriptions
                    topic = data.get("topic")
                    logger.info(f"Session {session.id} subscribed to topic: {topic}")
                    # TODO: Implement topic-based subscription

                elif message_type == "unsubscribe":
                    # Handle topic unsubscriptions
                    topic = data.get("topic")
                    logger.info(
                        f"Session {session.id} unsubscribed from topic: {topic}"
                    )
                    # TODO: Implement topic-based unsubscription

                elif message_type == "pong":
                    # Heartbeat response
                    continue

                else:
                    logger.warning(
                        f"Unknown message type '{message_type}' from session {session.id}"
                    )

            except asyncio.TimeoutError:
                # Send ping for heartbeat
                try:
                    await websocket.send_json({"type": "ping"})
                    # Wait for pong response
                    pong = await asyncio.wait_for(
                        websocket.receive_json(), timeout=10.0
                    )
                    if pong.get("type") != "pong":
                        logger.warning(
                            f"Expected pong from session {session.id}, got: {pong}"
                        )
                        break
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Session {session.id} did not respond to ping, disconnecting"
                    )
                    break

    except WebSocketDisconnect:
        logger.info(f"Session {session.id} disconnected normally")
    except Exception as e:
        logger.error(
            f"Error in unified WebSocket session {session.id}: {e}", exc_info=True
        )
    finally:
        # Cleanup
        if heartbeat_task:
            heartbeat_task.cancel()

        # Disconnect from manager (only if connection was established)
        if manager_connection_id is not None:
            try:
                manager.disconnect(manager_connection_id)
            except Exception as e:
                logger.error(f"Error disconnecting from manager: {e}")

        # End session (only if session was created)
        try:
            await session_manager.end_session(session.id, db)
        except Exception as e:
            logger.error(f"Error ending session: {e}")

        # Close WebSocket
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed

        logger.info(f"Unified WebSocket session {session.id} closed")
