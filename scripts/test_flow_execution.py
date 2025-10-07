import asyncio
from spacemodels.db.session import get_db_session

from spacebridge.services.flow_orchestrator import FlowExecutionOrchestrator
from spacesync.services.event_bus import get_nats_client


async def test_flow():
    # Get DB session - get_db_session() returns a generator, so we need to get the actual session
    db_gen = get_db_session()
    db = next(db_gen)

    try:
        # Trigger event data
        event_data = {
            "source": "github",
            "type": "push",
            "account_id": "af7c8558-9625-4e8a-af5b-5efe372b4b62",
            "payload": {
                "commit": {"sha": "abc123", "message": "Fix authentication bug"}
            },
        }

        # Get NATS client
        nats_client = await get_nats_client()

        # Create and run orchestrator
        orchestrator = FlowExecutionOrchestrator(
            db=db,
            flow_id="59cea56a-a3d5-4f94-a8a0-483bb4729014",
            trigger_event_data=event_data,
            nats_client=nats_client,
        )

        await orchestrator.run()
    finally:
        # Close the session
        try:
            next(db_gen)
        except StopIteration:
            pass


asyncio.run(test_flow())
