#!/usr/bin/env python3
"""Test script for flow execution."""

import argparse
import asyncio
import logging
import sys

from preloop.models.db.session import get_db_session
from preloop.models.models import Flow, Account
from preloop.services.flow_orchestrator import FlowExecutionOrchestrator
from preloop.sync.services.event_bus import EventBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def select_flow():
    """
    Display available flows and let user select one.

    Returns:
        Tuple of (flow_id, account_id) or (None, None) if cancelled
    """
    db_gen = get_db_session()
    db = next(db_gen)

    try:
        # Get all flows with their account information
        flows = (
            db.query(Flow, Account)
            .join(Account, Flow.account_id == Account.id)
            .order_by(Flow.created_at.desc())
            .all()
        )

        if not flows:
            print("No flows found in the database.")
            return None, None

        print("\n" + "=" * 80)
        print("Available Flows")
        print("=" * 80)

        for idx, (flow, account) in enumerate(flows, 1):
            status_icon = "✓" if flow.is_enabled else "✗"
            preset_marker = " [PRESET]" if flow.is_preset else ""
            print(f"\n{idx}. {status_icon} {flow.name}{preset_marker}")
            print(f"   ID: {flow.id}")
            print(f"   Account: {account.email} (ID: {account.id})")
            print(f"   Trigger: {flow.trigger_event_source}/{flow.trigger_event_type}")
            print(f"   Agent: {flow.agent_type}")
            if flow.description:
                print(f"   Description: {flow.description}")

        print("\n" + "=" * 80)
        print("Enter the number of the flow to execute (or 'q' to quit): ", end="")

        choice = input().strip()

        if choice.lower() == "q":
            print("Cancelled.")
            return None, None

        try:
            selection = int(choice)
            if 1 <= selection <= len(flows):
                flow, account = flows[selection - 1]
                print(f"\nSelected: {flow.name} (owned by {account.email})")
                return str(flow.id), str(account.id)
            else:
                print(
                    f"Invalid selection. Please enter a number between 1 and {len(flows)}."
                )
                return None, None
        except ValueError:
            print("Invalid input. Please enter a number or 'q' to quit.")
            return None, None

    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


async def test_flow(flow_id: str, account_id: str):
    """Test flow execution.

    Args:
        flow_id: UUID of the flow to execute
        account_id: UUID of the account that owns the flow
    """
    # Get DB session - get_db_session() returns a generator, so we need to get the actual session
    db_gen = get_db_session()
    db = next(db_gen)

    # Initialize event bus (reads URL from settings)
    event_bus = EventBus()

    try:
        # Connect to NATS
        logger.info("Connecting to NATS...")
        await event_bus.connect()
        logger.info(f"Connected to NATS at {event_bus.nats_url}")

        # Trigger event data
        event_data = {
            "source": "github",
            "type": "push",
            "account_id": account_id,
            "payload": {
                "commit": {"sha": "abc123", "message": "Fix authentication bug"}
            },
        }

        # Get NATS client from event bus
        nats_client = event_bus.nc

        # Create and run orchestrator
        logger.info(f"Creating flow orchestrator for flow {flow_id}...")
        orchestrator = FlowExecutionOrchestrator(
            db=db,
            flow_id=flow_id,
            trigger_event_data=event_data,
            nats_client=nats_client,
        )

        logger.info("Running flow execution...")
        await orchestrator.run()
        logger.info("Flow execution completed")

    except Exception as e:
        logger.error(f"Error during flow execution: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Close NATS connection
        try:
            await event_bus.close()
            logger.info("NATS connection closed")
        except Exception as e:
            logger.error(f"Error closing NATS: {e}")

        # Close the database session
        try:
            next(db_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test flow execution (interactive or with explicit IDs)"
    )
    parser.add_argument(
        "--flow-id",
        help="UUID of the flow to execute (optional, will prompt if not provided)",
    )
    parser.add_argument(
        "--account-id",
        help="UUID of the account that owns the flow (optional, will prompt if not provided)",
    )
    args = parser.parse_args()

    # If IDs not provided, use interactive selection
    flow_id = args.flow_id
    account_id = args.account_id

    if not flow_id or not account_id:
        flow_id, account_id = select_flow()
        if not flow_id or not account_id:
            sys.exit(0)

    asyncio.run(test_flow(flow_id, account_id))
