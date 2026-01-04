import asyncio
import json
import logging
import uuid
from typing import Dict

from fastapi import WebSocket
from nats.aio.client import Client
from nats.aio.msg import Msg

from preloop.sync.services.event_bus import get_task_publisher
from preloop.models.db.session import get_db_session as get_db

logger = logging.getLogger(__name__)


async def persist_execution_log(execution_id: str, log_data: dict):
    """
    Appends a log entry to the execution_logs array in the database.

    Args:
        execution_id: ID of the flow execution
        log_data: Log message data to append
    """
    try:
        from preloop.models.crud import crud_flow_execution

        db = next(get_db())
        try:
            # Use CRUD method to append log
            crud_flow_execution.append_log(
                db, execution_id=execution_id, log_data=log_data
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(
            f"Failed to persist log for execution {execution_id}: {e}", exc_info=True
        )


class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates with account-based filtering.
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_accounts: Dict[str, str] = {}  # connection_id -> account_id

    async def connect(self, websocket: WebSocket) -> str:
        """
        Accepts a new WebSocket connection and returns a unique ID for it.
        For backward compatibility - no account filtering.
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        logger.info(f"New WebSocket connection {connection_id} established.")
        logger.info(f"Total active connections: {len(self.active_connections)}")
        return connection_id

    async def connect_with_account(self, websocket: WebSocket, account_id: str) -> str:
        """
        Accepts a new WebSocket connection with account ID for filtering.

        Args:
            websocket: WebSocket connection
            account_id: Account ID for filtering broadcasts

        Returns:
            connection_id: Unique identifier for this connection
        """
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        self.connection_accounts[connection_id] = account_id
        logger.info(
            f"New WebSocket connection {connection_id} established for account {account_id}."
        )
        logger.info(f"Total active connections: {len(self.active_connections)}")
        return connection_id

    def disconnect(self, connection_id: str):
        """
        Disconnects a WebSocket and removes account association.
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"WebSocket connection {connection_id} closed.")

        if connection_id in self.connection_accounts:
            del self.connection_accounts[connection_id]

        logger.info(f"Total active connections: {len(self.active_connections)}")

    async def broadcast(self, message: str, account_id: str = None):
        """
        Broadcasts a message to connected clients, optionally filtered by account_id.

        Args:
            message: Message to broadcast
            account_id: If provided, only send to connections with matching account_id
        """
        sent_count = 0
        for connection_id, connection in list(self.active_connections.items()):
            # If account_id is specified, only send to connections with matching account
            if account_id is not None:
                conn_account = self.connection_accounts.get(connection_id)
                if conn_account != account_id:
                    continue

            try:
                await connection.send_text(message)
                sent_count += 1
                logger.debug(f"Sent message to connection {connection_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to send message to connection {connection_id}: {e}"
                )

        if account_id:
            logger.info(
                f"Broadcast complete: sent to {sent_count} connection(s) for account {account_id}"
            )

    async def broadcast_json(self, data: dict, account_id: str = None):
        """
        Broadcasts a JSON message to connected clients, optionally filtered by account_id.

        Args:
            data: Data to broadcast as JSON
            account_id: If provided, only send to connections with matching account_id
        """
        msg_type = data.get("type", "unknown")
        logger.info(
            f"Broadcasting JSON message type={msg_type} to account_id={account_id}, "
            f"active_connections={len(self.active_connections)}"
        )

        # Log matching connections for debugging
        if account_id:
            matching = [
                cid
                for cid, acc in self.connection_accounts.items()
                if acc == account_id
            ]
            logger.info(
                f"Connections matching account_id={account_id}: {len(matching)}"
            )

        await self.broadcast(json.dumps(data), account_id=account_id)


async def nats_consumer(manager: "WebSocketManager"):
    """
    Consumes messages from NATS and broadcasts them to WebSocket clients.
    Includes account-based filtering for security - only broadcasts to clients
    with matching account_id.
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

            # Extract account_id for filtering
            account_id = data.get("account_id")

            # Persist log messages to database
            execution_id = data.get("execution_id")
            if execution_id:
                await persist_execution_log(execution_id, data)

            # Broadcast to WebSocket clients with account filtering
            # Only clients with matching account_id will receive the message
            if account_id:
                await manager.broadcast_json(data, account_id=str(account_id))
            else:
                # If no account_id in message, log warning but still broadcast
                # (for backward compatibility during migration)
                logger.warning(
                    f"Flow update message missing account_id: {data.get('type')} "
                    f"for execution {execution_id}"
                )
                await manager.broadcast_json(data)

        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message from NATS: {msg.data.decode()}")
        except Exception as e:
            logger.error(f"Error processing NATS message: {e}")

    try:
        # Subscribe to a wildcard subject to receive all flow updates
        flow_sub = await nats_client.subscribe("flow-updates.*", cb=message_handler)
        logger.info("Subscribed to NATS subject 'flow-updates.*'")

        # Subscribe to approval updates
        approval_sub = await nats_client.subscribe(
            "approval-updates", cb=message_handler
        )
        logger.info("Subscribed to NATS subject 'approval-updates'")

        # Subscribe to admin activity updates (for admin dashboard)
        activity_sub = await nats_client.subscribe("admin.activity", cb=message_handler)
        logger.info("Subscribed to NATS subject 'admin.activity'")

        # Keep the consumer running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"NATS consumer failed: {e}")


# Create a single instance of the manager to be used across the application
manager = WebSocketManager()
